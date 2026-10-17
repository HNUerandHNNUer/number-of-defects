#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fast SSD pipeline: PyMOL PNG batches -> ordered OpenCV AVI while rendering.

Real jobs are only published after all frames have rendered and the video has
been encoded, validated and copied to its final destination. Existing completed
videos are not overwritten except with --overwrite. GUI JSON events plus tqdm.
No frames dropped, no change to color, camera, ray tracing or codec settings.
In contrast to the old two-pass renderer, encoding overlaps rendering, with a
bounded number of temporary PNG files and deterministic time-step ordering.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid

try:
    from tqdm.auto import tqdm
except ImportError:
    tqdm = None

PREFIX = '@@DEFECT_PROGRESS@@'
PRINT_LOCK = threading.RLock()
STAGE_LOCK = threading.Lock()  # serialize reads from the E: HDD, while other jobs render on SSD
STOP = threading.Event()
F_PATTERN = re.compile(r'^F_(\d+(?:\.\d+)?)(?:_.*)?$', re.I)
XYZ_PATTERN = re.compile(r'^defect_out-(\d+)\.xyz$', re.I)
DEFAULT_PARENT = r'E:\1\7.9.2025\3000\phi_0.7\number of defects\new'


class Cancelled(Exception):
    pass


def say(*args):
    with PRINT_LOCK:
        print(*args, flush=True)


def cancel_if_needed(cancel_file):
    if STOP.is_set() or (cancel_file and Path(cancel_file).exists()):
        STOP.set()
        raise Cancelled('User requested cancellation')


def handle_signal(sig, _frame):
    STOP.set()


class Reporter:
    """Batch per-frame JSON events to reduce pipe/UI overhead; tqdm in CLI."""
    def __init__(self, count, total, gui=False):
        self.gui = gui
        self.lock = threading.Lock()
        self.total = total
        self.pending = {}
        self.last = time.monotonic()
        self.bars = {}
        if tqdm and not gui:
            for stage in ('copy', 'render', 'encode'):
                self.bars[stage] = tqdm(total=total, desc=stage, unit='frame', mininterval=.3)

    def event(self, event, **data):
        if self.gui:
            with PRINT_LOCK:
                print(PREFIX + json.dumps({'event': event, **data}, ensure_ascii=False, separators=(',', ':')),
                      flush=True)

    def frame(self, name, stage, n=1):
        with self.lock:
            if stage in self.bars:
                self.bars[stage].update(n)
            key = (name, stage)
            self.pending[key] = self.pending.get(key, 0) + n
            now = time.monotonic()
            if self.pending[key] >= 20 or now - self.last >= .5:
                count = self.pending.pop(key)
                self.event('frame', name=name, stage=stage, delta=count)
                self.last = now

    def flush(self):
        with self.lock:
            for (name, stage), count in list(self.pending.items()):
                self.event('frame', name=name, stage=stage, delta=count)
            self.pending.clear()

    def close(self):
        self.flush()
        for bar in self.bars.values():
            bar.close()


def discover(root):
    jobs = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue
        match = F_PATTERN.fullmatch(folder.name)
        if not match:
            continue
        for defect in sorted(folder.rglob('defect_out')):
            if not defect.is_dir():
                continue
            files = []
            for path in defect.iterdir():
                if path.is_file():
                    m = XYZ_PATTERN.fullmatch(path.name)
                    if m:
                        files.append((int(m.group(1)), path))
            files.sort(key=lambda p: (p[0], p[1].name))
            if not files:
                say('[SKIP] No XYZ:', defect)
                continue
            if len({step for step, _ in files}) != len(files):
                raise ValueError('Duplicate XYZ timestep under ' + str(defect))
            jobs.append({'root': root, 'folder': folder, 'source': defect,
                         'value': match.group(1), 'files': files})
    jobs.sort(key=lambda p: (float(p['value']), str(p['folder']), str(p['source'])))
    freq = Counter(job['value'] for job in jobs)
    for job in jobs:
        part = job['value']
        if freq[part] > 1:
            suffix = str(job['source'].relative_to(job['root']).parent)
            part += '__' + safe_name(suffix.replace('\\', '__').replace('/', '__'))
        job['stem'] = part
    return jobs


def safe_name(value):
    return re.sub(r'[^a-zA-Z0-9_.-]+', '_', value).strip('._')


def imread_win(path, cv2, np):
    data = np.fromfile(str(path), dtype=np.uint8)
    frame = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if frame is None:
        raise RuntimeError('Cannot read PNG: ' + str(path))
    if frame.ndim == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    if frame.shape[2] == 4:
        bgr = frame[:, :, :3].astype(np.float32)
        alpha = frame[:, :, 3:4].astype(np.float32) / 255
        return np.clip(bgr * alpha + 255 * (1 - alpha), 0, 255).astype(np.uint8)
    return frame


def verify_video(path, nframes, width, height):
    import cv2
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise RuntimeError('OpenCV cannot open output video: ' + str(path))
        n = int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
        w = int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH)))
        h = int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        if (w, h) != (width, height):
            raise RuntimeError(f'Video dimensions {w}x{h} != {width}x{height}')
        # Strict check when frame count metadata is available. Corrupt/truncated
        # formats are NOT silently published if they report fewer frames.
        if n > 0 and n != nframes:
            raise RuntimeError(f'Encoded video reports {n} frames, expected {nframes}')
        ok, _ = capture.read()
        if not ok:
            raise RuntimeError('Cannot decode first video frame')
    finally:
        capture.release()


def render_encode_pipeline(executable, script, work, frames, args, name, reporter):
    """Bounded producer-consumer renderer/encoder.

    (1) Ray-trace first frame once, establishing the shared camera.
    (2) Spawn PyMOL workers on fixed-size sequential chunks. Unlike the old
        one-chunk-per-worker approach, at most 2*workers chunks are queued.
    (3) As soon as the next chronological chunk finishes, append its frames
        to a single VideoWriter and optionally delete its PNGs immediately.
    (4) Rendering later chunks continues while encoding the previous chunk.

    No dropped/repeated frames, changed colors, separate lossy AVI segments,
    GPU codec substitution, or weakened physics/camera settings.
    """
    import cv2
    import numpy as np

    video = work / ('encoded.' + args.format)
    out_frames = len(frames)
    if not out_frames:
        raise RuntimeError('No frames to encode')
    worker_count = max(1, int(args.frame_workers))
    chunk_len = max(8, int(args.chunk_frames))
    writer = None
    written = 0
    try:
        camera_path = work / 'camera.json'
        seed = make_manifest(work, frames[:1], args, 'seed', camera_output=camera_path)
        launch_pymol(executable, script, seed, name + ':seed', name, args, reporter)
        camera = json.loads(camera_path.read_text(encoding='utf-8'))
        if not isinstance(camera, list) or len(camera) != 18:
            raise RuntimeError('Invalid camera: expected 18 matrix parameters')

        fourccs = ['mp4v'] if args.format == 'mp4' else ['XVID', 'MJPG']
        for codec in fourccs:
            candidate = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*codec),
                                        args.fps, (args.width, args.height))
            if candidate.isOpened():
                writer = candidate
                say('[CODEC]', name, codec)
                break
            candidate.release()
        if writer is None:
            raise RuntimeError('Cannot initialize OpenCV VideoWriter')

        def consume(items):
            nonlocal written
            for item in items:
                cancel_if_needed(args.cancel_file)
                path = Path(item['target'])
                if not path.is_file() or path.stat().st_size == 0:
                    raise RuntimeError('Missing/empty rendered PNG: ' + str(path))
                image = imread_win(path, cv2, np)
                if (image.shape[1], image.shape[0]) != (args.width, args.height):
                    raise RuntimeError('Incorrect PNG size: ' + str(path))
                writer.write(image)
                written += 1
                reporter.frame(name, 'encode')
                if not args.keep_png:
                    path.unlink()
                if written == 1 or written % 250 == 0 or written == out_frames:
                    say('[PIPELINE]', name, f'encoded={written}/{out_frames}')

        consume(frames[:1])
        chunks = [frames[start:start + chunk_len]
                  for start in range(1, out_frames, chunk_len)]
        # Bounded in-flight scheduling is important: an early chunk may take
        # longer, but later workers must not fill the SSD with 10,000 PNGs.
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            in_flight = {}
            next_chunk = 0

            def submit_chunk(index):
                chunk = chunks[index]
                manifest = make_manifest(work, chunk, args, f'chunk_{index:06d}',
                                         fixed_camera=camera)
                return executor.submit(launch_pymol, executable, script, manifest,
                                       f'{name}:chunk{index + 1}', name, args, reporter)

            for _ in range(min(worker_count * 2, len(chunks))):
                in_flight[next_chunk] = submit_chunk(next_chunk)
                next_chunk += 1
            for current, chunk in enumerate(chunks):
                cancel_if_needed(args.cancel_file)
                in_flight.pop(current).result()  # preserve EXACT frame order
                consume(chunk)
                if next_chunk < len(chunks):
                    in_flight[next_chunk] = submit_chunk(next_chunk)
                    next_chunk += 1
        writer.release()
        writer = None
        if written != out_frames:
            raise RuntimeError(f'Expected {out_frames} frames, encoded {written}')
        if not video.is_file() or video.stat().st_size == 0:
            raise RuntimeError('Empty video after encoding')
        verify_video(video, out_frames, args.width, args.height)
        return video
    finally:
        if writer is not None:
            writer.release()

def make_manifest(work, frames, args, suffix, camera_output=None, fixed_camera=None):
    job = {'frames': frames, 'width': args.width, 'height': args.height,
           'beads_per_chain': args.beads_per_chain, 'boundary': args.boundary,
           'ray': args.ray, 'ray_threads': args.ray_threads_effective,
           'cancel_file': args.cancel_file}
    if camera_output is not None:
        job['camera_output'] = str(camera_output)
    if fixed_camera is not None:
        job['fixed_camera'] = fixed_camera
    target = work / (suffix + '.json')
    target.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
    return target


def launch_pymol(executable, script, task, label, name, args, reporter):
    cancel_if_needed(args.cancel_file)
    env = os.environ.copy()
    env['DEFECT_VIDEO_JOB'] = str(task)
    for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        env[variable] = '1'
    argv = [executable, '-cq', '-r', str(script)]
    say('[PYMOL START]', label, subprocess.list2cmdline(argv))
    p = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, text=True, encoding='utf-8',
                         errors='replace', bufsize=1)
    try:
        for line in p.stdout:
            line = line.rstrip('\r\n')
            if line == '@@PYMOL_FRAME@@':
                reporter.frame(name, 'render')
            elif line.startswith('Ray: render time:'):
                pass  # Very high-frequency PyMOL noise; progress provides real counts
            elif line:
                say('[' + label + ']', line)
        p.stdout.close()
        code = p.wait()
    finally:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
    cancel_if_needed(args.cancel_file)
    if code:
        raise RuntimeError(f'PyMOL {label} exited with code {code}')


def stage_xyz(job, work, args, reporter, name):
    targetdir = work / 'xyz'
    targetdir.mkdir()
    new_files = []
    with STAGE_LOCK:
        cancel_if_needed(args.cancel_file)
        say('[SSD COPY]', job['source'], '->', targetdir)
        estimated = sum(path.stat().st_size for _, path in job['selected'])
        free = shutil.disk_usage(work).free
        # Do not saturate the SSD: reserve at least 5 GiB for PNG and video
        # (still not a guarantee of sufficient space for arbitrarily large jobs).
        if free < estimated + (5 << 30):
            raise RuntimeError(f'Insufficient SSD space: free={free/(1<<30):.1f} GiB, '
                               f'XYZ={estimated/(1<<30):.1f} GiB; leave >=5 GiB extra')
        for i, (step, source) in enumerate(job['selected'], 1):
            cancel_if_needed(args.cancel_file)
            output = targetdir / source.name
            shutil.copyfile(source, output)
            if output.stat().st_size != source.stat().st_size:
                raise IOError('Staged XYZ size mismatch: ' + str(source))
            new_files.append((step, output))
            reporter.frame(name, 'copy')
            if i == 1 or i % 500 == 0 or i == len(job['selected']):
                say('[COPY]', name, f'{i}/{len(job["selected"])}')
    return new_files


def publish(from_cache, target, args):
    """Final file becomes visible atomically, only after SSD copy succeeded."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name('.' + target.stem + '.partial-' + uuid.uuid4().hex + target.suffix)
    try:
        cancel_if_needed(args.cancel_file)
        with open(from_cache, 'rb') as source, open(partial, 'wb') as dest:
            while True:
                cancel_if_needed(args.cancel_file)
                buf = source.read(4 << 20)
                if not buf:
                    break
                dest.write(buf)
            dest.flush()
            os.fsync(dest.fileno())
        if from_cache.stat().st_size != partial.stat().st_size:
            raise IOError('Copy to final directory was truncated')
        cancel_if_needed(args.cancel_file)
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)


def process_job(job, seq, count, args, executable, script, reporter, active_workspace):
    target = job['target']
    name = job['key']
    nframes = len(job['selected'])
    if target.is_file() and target.stat().st_size > 0 and not args.overwrite:
        try:
            verify_video(target, nframes, args.width, args.height)
        except Exception as exc:
            say('[FAIL] Existing output does not match request:', target, exc)
            reporter.event('job_end', name=name, status='failed', error='已有视频帧数/尺寸不同或无法解码；请勾选覆盖后重新运行: ' + str(exc))
            return 'failed', str(target)
        say('[SKIP] Verified existing:', target)
        reporter.flush()
        reporter.event('job_end', name=name, status='skipped', path=str(target))
        return 'skipped', str(target)
    reporter.event('job_start', name=name)
    t0 = time.monotonic()
    work = None
    try:
        cancel_if_needed(args.cancel_file)
        work = Path(tempfile.mkdtemp(prefix='job_', dir=str(active_workspace)))
        t_copy = time.monotonic()
        cached = stage_xyz(job, work, args, reporter, name)
        copy_seconds = time.monotonic() - t_copy
        images = work / 'png'
        images.mkdir()
        frames = [{'source': str(src), 'target': str(images / ('defect_%010d.png' % step))}
                  for step, src in cached]
        reporter.event('job_phase', name=name, status='rendering')
        t_pipeline = time.monotonic()
        video = render_encode_pipeline(executable, script, work, frames, args, name, reporter)
        pipeline_seconds = time.monotonic() - t_pipeline
        cancel_if_needed(args.cancel_file)
        reporter.event('job_phase', name=name, status='publishing')
        t_publish = time.monotonic()
        with STAGE_LOCK:  # avoid simultaneous high-throughput E: reads/writes
            publish(video, target, args)
        publish_seconds = time.monotonic() - t_publish
        say('[TIMING]', name, f'copy={copy_seconds:.1f}s',
            f'render+encode={pipeline_seconds:.1f}s',
            f'publish={publish_seconds:.1f}s',
            f'pipeline_rate={nframes / max(pipeline_seconds, 1e-6):.2f} frames/s')
        say('[SUCCESS]', target, f'elapsed={time.monotonic()-t0:.1f}s', 'frames=', nframes)
        reporter.flush()
        reporter.event('job_end', name=name, status='success', path=str(target))
        if args.keep_png:
            # Optional copy; failures do not invalidate the published video.
            dest = target.parent / 'png_frames' / safe_name(job['root'].name + '_' + job['folder'].name)
            if dest.exists():
                say('[WARN] PNG save skipped, destination exists:', dest)
            else:
                try:
                    shutil.copytree(images, dest)
                    say('[PNG SAVED]', dest)
                except OSError as exc:
                    say('[WARN] Video succeeded, PNG archive failed:', exc)
        return 'success', str(target)
    except Cancelled:
        say('[CANCELLED]', name)
        reporter.flush()
        reporter.event('job_end', name=name, status='cancelled')
        return 'cancelled', name
    except Exception as exc:
        say('[FAILED]', name, repr(exc))
        reporter.flush()
        reporter.event('job_end', name=name, status='failed', error=str(exc))
        return 'failed', f'{name}: {exc}'
    finally:
        if work is not None:
            try:
                shutil.rmtree(work)
            except OSError as exc:
                say('[WARN] SSD cache cleanup deferred:', work, exc)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', action='append', help='nchain root; repeat for several roots')
    p.add_argument('--output', default=None, help='Explicit output directory for exactly ONE root')
    p.add_argument('--output-base', default=None,
                   help='For multiple roots: <output-base>/<nchain-folder-name>/video')
    p.add_argument('--cache-dir', default='auto', help='auto: try writable D: cache, then user-owned LOCALAPPDATA cache')
    p.add_argument('--pymol', default='pymol')
    p.add_argument('--jobs', type=int, default=2)
    p.add_argument('--frame-workers', type=int, default=3)
    p.add_argument('--chunk-frames', type=int, default=256,
                   help='Frames per PyMOL batch; bounded streaming pipeline')
    p.add_argument('--cpu-cores', type=int, default=0)
    p.add_argument('--ray-threads', type=int, default=0)
    p.add_argument('--format', choices=['avi', 'mp4'], default='avi')
    p.add_argument('--fps', type=float, default=12)
    p.add_argument('--width', type=int, default=800)
    p.add_argument('--height', type=int, default=800)
    p.add_argument('--stride', type=int, default=1)
    p.add_argument('--max-frames', type=int, default=0)
    p.add_argument('--beads-per-chain', type=int, default=30)
    p.add_argument('--ray', type=int, choices=[0, 1], default=1)
    p.add_argument('--boundary', action='store_true')
    p.add_argument('--overwrite', action='store_true')
    p.add_argument('--keep-png', action='store_true')
    p.add_argument('--only', default=None)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--progress-json', action='store_true')
    p.add_argument('--cancel-file', default=None)
    args = p.parse_args(argv)
    if not args.root:
        p.error('At least one --root is required')
    if args.output and len(args.root) > 1:
        p.error('--output accepts one root only; use --output-base for multiple roots')
    if any([args.jobs < 1, args.frame_workers < 1, args.cpu_cores < 0,
            args.ray_threads < 0, args.chunk_frames < 8, args.stride < 1, args.max_frames < 0,
            args.fps <= 0, args.width < 2, args.height < 2,
            args.width % 2, args.height % 2, args.beads_per_chain < 2]):
        p.error('Invalid CPU, video dimensions, frame, or rendering parameter')
    return args



def prepare_cache(configured):
    """Probe real write permission; WinError 5 on D:/ no longer crashes jobs.

    Do not need admin permissions. An automatic fallback may be on C: SSD.
    Never choose E: HDD unless the user explicitly requests it.
    """
    if configured.strip().lower() == 'auto':
        candidates = []
        if os.name == 'nt' and Path('D:/').is_dir():
            candidates.append(Path('D:/DefectVideo_Cache'))
        local = os.environ.get('LOCALAPPDATA')
        candidates.append((Path(local) if local else Path.home() / 'AppData' / 'Local') / 'DefectVideo_Cache')
    else:
        candidates = [Path(configured).expanduser()]
        local = os.environ.get('LOCALAPPDATA')
        backup = (Path(local) if local else Path.home() / 'AppData' / 'Local') / 'DefectVideo_Cache'
        if str(backup).casefold() != str(candidates[0]).casefold():
            candidates.append(backup)
    problems = []
    for folder in candidates:
        try:
            folder = folder.resolve()
            folder.mkdir(parents=True, exist_ok=True)
            # Writing a file checks effective access, not only mkdir success.
            with tempfile.NamedTemporaryFile(prefix='.write_test_', dir=folder, delete=True) as tmp:
                tmp.write(b'ssd-check')
                tmp.flush()
            free = shutil.disk_usage(folder).free
            if free < (5 << 30):
                raise OSError(f'free space only {free / (1 << 30):.1f} GiB (<5 GiB)')
            say('[CACHE READY]', folder, f'free={free / (1 << 30):.1f} GiB')
            return folder
        except (OSError, PermissionError) as exc:
            problems.append(f'{folder}: {exc}')
            say('[CACHE UNAVAILABLE]', str(folder), str(exc))
    raise RuntimeError('No writable cache with >=5 GiB free. Please choose a writable SSD folder. '
                       + ' | '.join(problems))

def main(argv=None):
    args = parse_args(argv)
    # These signals also work for terminal Ctrl+C on Linux/macOS. Windows GUI
    # stop uses a cancellation file checked between copy, frames and encoding.
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    roots = [Path(r).expanduser().resolve() for r in args.root]
    if len(set(roots)) != len(roots):
        raise ValueError('Repeated root directory in input')
    alljobs = []
    root_destinations = []
    for root in roots:
        if not root.is_dir():
            raise FileNotFoundError('Root does not exist: ' + str(root))
        if args.output:
            out = Path(args.output).expanduser().resolve()
        elif args.output_base:
            out = Path(args.output_base).expanduser().resolve() / root.name / 'video'
        else:
            out = root / 'video'
        root_destinations.append(out)
        for job in discover(root):
            if args.only and job['folder'].name.lower() != args.only.lower():
                continue
            job['selected'] = job['files'][::args.stride]
            if args.max_frames:
                job['selected'] = job['selected'][:args.max_frames]
            job['target'] = out / (job['stem'] + '.' + args.format)
            job['key'] = root.name + '/' + str(job['source'].relative_to(root)).replace('\\', '/')
            alljobs.append(job)
    if len({str(x).lower() for x in root_destinations}) != len(root_destinations):
        raise ValueError('Two roots would output into the same folder; use separate output-base paths')
    if len({str(j['target']).lower() for j in alljobs}) != len(alljobs):
        raise ValueError('Output name collisions; inspect duplicated F_* folders')
    if not alljobs:
        raise RuntimeError('No F_*/**/defect_out/defect_out-NNN.xyz data found')
    total = sum(len(j['selected']) for j in alljobs)
    reporter = Reporter(len(alljobs), total, args.progress_json)
    say('[ROOTS]', len(roots), 'conditions=', len(alljobs), 'frames=', total)
    for job in alljobs:
        say('[PLAN]', job['key'], len(job['selected']), '/', len(job['files']), '->', job['target'])
        reporter.event('plan', name=job['key'], root=job['root'].name,
                       folder=job['folder'].name, frames=len(job['selected']),
                       path=str(job['target']))
    if args.dry_run:
        reporter.event('preview_end', count=len(alljobs), total=total)
        reporter.close()
        say('[DONE] Dry run. No files created.')
        return 0
    script = Path(__file__).resolve().with_name('render_defect_pymol.py')
    if not script.is_file():
        raise FileNotFoundError('render_defect_pymol.py missing beside main program')
    exe = shutil.which(args.pymol) or (str(Path(args.pymol)) if Path(args.pymol).is_file() else None)
    if not exe:
        raise FileNotFoundError('PyMOL CLI not found; set --pymol full path to pymol.EXE')
    cache = prepare_cache(args.cache_dir)
    # Create unique run cache, no reuse of potentially incomplete stale runs.
    run_cache = Path(tempfile.mkdtemp(prefix='defect_run_', dir=str(cache)))
    args.ray_threads_effective = (args.ray_threads or max(1, (args.cpu_cores or os.cpu_count() or 4)
                                                             // (args.jobs * args.frame_workers)))
    say('[PARALLEL]', f'{args.jobs} jobs x {args.frame_workers} workers',
        '[RAY THREADS]', args.ray_threads_effective, '[SSD]', run_cache)
    results = []
    try:
        with ThreadPoolExecutor(max_workers=min(args.jobs, len(alljobs))) as pool:
            futs = [pool.submit(process_job, job, i, len(alljobs), args,
                                exe, script, reporter, run_cache)
                    for i, job in enumerate(alljobs, 1)]
            for f in as_completed(futs):
                try:
                    results.append(f.result())
                except Exception as exc:
                    results.append(('failed', str(exc)))
                    say('[UNEXPECTED]', repr(exc))
    finally:
        reporter.close()
        try:
            run_cache.rmdir()
        except OSError:
            say('[WARN] Cache not empty (e.g. crash), inspect:', run_cache)
    summary = Counter(status for status, _ in results)
    reporter.event('finished', success=summary['success'], skipped=summary['skipped'],
                   failed=summary['failed'], cancelled=summary['cancelled'], count=len(alljobs))
    say('[SUMMARY]', dict(summary))
    for kind, item in results:
        if kind == 'failed':
            say('[FAILED]', item)
    return 130 if summary['cancelled'] else (1 if summary['failed'] else 0)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
