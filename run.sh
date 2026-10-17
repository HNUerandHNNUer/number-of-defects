#!/usr/bin/env bash
# Compatible live post-processing for the original sphere_nematic_parallel.py.
# Does not require --watch, --stable-seconds or the newer Python sources.
# Converted out-*.xyz are NEVER run through convert_lammps_to_bd.py again.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
export ROOT PYTHON_BIN
exec "$PYTHON_BIN" -u - <<'PY'
from __future__ import annotations
import csv
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(os.environ['ROOT']).resolve()
PYTHON = os.environ['PYTHON_BIN']
SPHERE = ROOT / 'sphere_nematic_parallel.py'
AVERAGE = ROOT / 'average_defects.py'


def integer(name, default, lowest):
    value = int(os.getenv(name, str(default)))
    if value < lowest:
        raise SystemExit(f'{name} must be >= {lowest}')
    return value


def real(name, default, positive=False):
    value = float(os.getenv(name, str(default)))
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise SystemExit(f'Invalid {name}: {value}')
    return value


def flag(name, default=False):
    s = os.getenv(name, '1' if default else '0').lower().strip()
    if s not in ('1', '0', 'yes', 'no', 'true', 'false'):
        raise SystemExit(f'Invalid {name}: use 0 or 1')
    return s in ('1', 'yes', 'true')


RUN_ONCE = flag('RUN_ONCE')
ONLY_F = os.getenv('ONLY_F', '').strip()
CHAIN_LENGTH = integer('CHAIN_LENGTH', 30, 2)
WORKERS = integer('DEFECT_WORKERS', 2, 0)
STABLE_SECONDS = real('STABLE_SECONDS', 10)
SCAN_INTERVAL_SECONDS = real('SCAN_INTERVAL_SECONDS', 30, True)
FRAME_TIMEOUT_SECONDS = real('FRAME_TIMEOUT_SECONDS', 600, True)
BATCH_TIMEOUT_SECONDS = real('BATCH_TIMEOUT_SECONDS', 1800, True)
BATCH_SIZE = integer('BATCH_SIZE', 8, 1)
MAX_NEW_PER_FOLDER = integer('MAX_NEW_PER_FOLDER', 32, 1)
PUBLISH_EVERY_NEW = integer('PUBLISH_EVERY_NEW', 32, 1)
PUBLISH_INTERVAL_SECONDS = real('PUBLISH_INTERVAL_SECONDS', 300)
DO_AVERAGE = flag('DO_AVERAGE', True)
if sys.version_info < (3, 8):
    raise SystemExit('Need Python >= 3.8')
if not SPHERE.is_file():
    raise SystemExit(f'Missing analysis source: {SPHERE}')


def log(line):
    print(line, flush=True)


def atomic_text(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('w', encoding='utf-8', newline='\n') as f:
            f.write(data)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def save_json(path, obj):
    atomic_text(path, json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def read_json(path, fallback=None):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return {} if fallback is None else fallback


def signature(path):
    s = path.stat()
    return {'size': s.st_size, 'mtime_ns': s.st_mtime_ns,
            'inode': getattr(s, 'st_ino', 0)}


def mature(sig):
    return (sig['size'] > 0 and time.time_ns() - sig['mtime_ns'] >= STABLE_SECONDS * 1.e9)


def timestep(path):
    match = re.fullmatch(r'out-(\d+)\.xyz', path.name)
    return int(match.group(1)) if match else None


def xyz_kind(path):
    with path.open('rb') as f:
        first = f.readline(128).decode('utf-8-sig', 'replace').strip()
        second = f.readline(512).decode('utf-8', 'replace')
    if first == 'ITEM: TIMESTEP':
        return 'raw'
    if first.isdecimal() and int(first) > 0 and 'Timestep:' in second and 'BoxSize:' in second:
        return 'converted'
    return 'pending'


def stable_snapshot(source, target, sig):
    """Read an independent frozen copy, never touching the live original."""
    if not mature(sig):
        return False, 'still being written'
    try:
        with source.open('rb') as src, target.open('wb') as dst:
            shutil.copyfileobj(src, dst, length=1 << 20)
        if signature(source) != sig or target.stat().st_size != sig['size']:
            return False, 'file changed during snapshot'
        # Strict converted-format structural verification before invoking old worker.
        with target.open('r', encoding='utf-8-sig') as f:
            n_text = f.readline().strip()
            if not n_text.isdecimal() or int(n_text) <= 0:
                return False, 'not converted XYZ'
            n = int(n_text)
            header = f.readline()
            match = re.search(r'Timestep:\s*(-?\d+)', header)
            if (match is None or int(match.group(1)) != timestep(source)
                    or 'BoxSize:' not in header):
                return False, 'header timestep or BoxSize inconsistent'
            box_tokens = header.split('BoxSize:', 1)[1].split()
            if len(box_tokens) != 3 or any(not math.isfinite(float(v)) or float(v) <= 0
                                           for v in box_tokens):
                return False, 'invalid box lengths'
            count = 0
            for row in f:
                parts = row.split()
                if len(parts) != 4:  # exactly type, x, y, z, matching legacy code
                    return False, 'non-four-column XYZ row'
                count += 1
                if count > n:
                    return False, 'more XYZ rows than specified'
            if count != n:
                return False, f'partial XYZ: {count}/{n} atom rows'
        if signature(source) != sig:
            return False, 'file changed during verification'
        return True, ''
    except (OSError, UnicodeError, ValueError) as exc:
        return False, f'incomplete/invalid file: {exc}'


def call_sphere(folder, input_dir, output_dir, xyz_dir):
    cmd = [PYTHON, '-u', str(SPHERE),
           '--input-dir', str(input_dir), '--pattern', 'out-*.xyz',
           '--output', str(output_dir), '--xyz-output', str(xyz_dir),
           '--chain-length', str(CHAIN_LENGTH), '--workers', str(WORKERS),
           '--timeout', str(FRAME_TIMEOUT_SECONDS)]
    log(f'    [compute] legacy-compatible sphere, batch inputs={len(list(input_dir.glob("out-*.xyz")))}')
    p = subprocess.Popen(cmd, cwd=str(folder), start_new_session=True)
    try:
        return p.wait(timeout=BATCH_TIMEOUT_SECONDS)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        log(f'    [timeout/interrupted] stopping ONLY the launched Python process group PID={p.pid}')
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.wait(timeout=5)
        if sys.exc_info()[0] is KeyboardInterrupt:
            raise
        return 124


def parse_batch_results(input_paths, out, xyz):
    expected = {timestep(p): p for p in input_paths}
    defect_file = out / 'defect_results.dat'
    delaunay_file = out / 'delaunay.dat'
    if not defect_file.is_file() or not delaunay_file.is_file():
        raise ValueError('Batch output DAT missing')
    with defect_file.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        headers = reader.fieldnames or []
        if not all(k in headers for k in ('timestep', 'net_charge', 'total_defects')):
            raise ValueError('Unexpected defect_results.dat schema')
        found = {}
        for row in reader:
            step = int(row['timestep'])
            if step not in expected or step in found:
                raise ValueError('Wrong or duplicate timestep in defect_results.dat')
            total = int(row['total_defects'])
            counts = {key: int(value) for key, value in row.items()
                      if key not in ('timestep', 'net_charge', 'total_defects')}
            if total < 0 or any(x < 0 for x in counts.values()):
                raise ValueError('Negative defect count')
            if sum(counts.values()) != total:
                raise ValueError('Defect counts do not sum to total')
            found[step] = {'counts': counts, 'net_charge': row['net_charge'], 'total': total}
    if set(found) != set(expected):
        raise ValueError('Batch result missing one or more timesteps')
    for step, path in expected.items():
        if not (xyz / ('defect_' + path.stem + '.xyz')).is_file():
            raise ValueError(f'XYZ defect output missing for timestep {step}')
    return found, delaunay_file


def cache_one(meta_dir, xyz_dest, source, sig, revision, record, dat_file, xyz_file):
    stem = source.stem
    cache_dat = meta_dir / (stem + '.dat')
    cache_json = meta_dir / (stem + '.json')
    xyz_target = xyz_dest / xyz_file.name
    if signature(source) != sig:
        log(f'    [defer] {source.name}: changed during computation')
        return False
    # Atomic publication per file; JSON metadata is the LAST commit marker.
    os.replace(dat_file, cache_dat)
    temp_xyz = xyz_target.with_name('.pending_' + uuid.uuid4().hex + '.xyz')
    try:
        shutil.copyfile(xyz_file, temp_xyz)
        os.replace(temp_xyz, xyz_target)
    finally:
        temp_xyz.unlink(missing_ok=True)
    info = {'revision': revision, 'signature': sig, 'timestep': timestep(source),
            'record': record, 'dat': cache_dat.name, 'xyz': xyz_file.name}
    save_json(cache_json, info)
    return True


def process_group(paths, sigs, folder, meta_dir, xyz_dest, revision, failures):
    """Batch old unmodified analysis engine; bisect bad batches to isolate invalid frames."""
    if not paths:
        return 0
    # Temporary directory on the same filesystem for safe atomic cache operations.
    with tempfile.TemporaryDirectory(prefix='.sphere_batch_', dir=str(meta_dir.parent)) as d:
        work = Path(d)
        inputs = work / 'inputs'
        output = work / 'results'
        xyz = work / 'defect_out'
        inputs.mkdir()
        active = []
        for path in paths:
            dest = inputs / path.name
            okay, why = stable_snapshot(path, dest, sigs[path.name])
            if okay:
                active.append(path)
            else:
                log(f'    [pending] {path.name}: {why}')
                dest.unlink(missing_ok=True)
        if not active:
            return 0
        status = call_sphere(folder, inputs, output, xyz)
        if status == 0:
            try:
                found, delaunay = parse_batch_results(active, output, xyz)
                # Each face row is copied byte-for-byte into its frame-specific cache.
                step_parts = {}
                with delaunay.open('rb') as f:
                    headline = f.readline()
                    if not headline.startswith(b'# timestep '):
                        raise ValueError('Unexpected delaunay.dat header')
                    for row in f:
                        if not row.strip():
                            continue
                        step = int(row.split(None, 1)[0])
                        if step not in found:
                            raise ValueError('Unknown timestep in delaunay.dat')
                        if step not in step_parts:
                            part = work / f'face_{step}.dat'
                            step_parts[step] = part.open('wb')
                        step_parts[step].write(row)
                for fp in step_parts.values():
                    fp.close()
                if set(step_parts) != set(found):
                    raise ValueError('Missing triangulation rows')
                committed = 0
                for src in active:
                    step = timestep(src)
                    candidate = work / f'face_{step}.dat'
                    output_xyz = xyz / ('defect_' + src.stem + '.xyz')
                    if cache_one(meta_dir, xyz_dest, src, sigs[src.name], revision,
                                 found[step], candidate, output_xyz):
                        failures.pop(src.name, None)
                        committed += 1
                log(f'    [saved] {committed} new frame(s)')
                return committed
            except (OSError, ValueError, TypeError) as exc:
                log(f'    [bad-output] {exc}; isolate the problem frame(s)')
                status = 1
    # The old analyzer stops on the first invalid frame. Try smaller groups.
    if len(active) > 1:
        midpoint = len(active) // 2
        return (process_group(active[:midpoint], sigs, folder, meta_dir, xyz_dest,
                              revision, failures) +
                process_group(active[midpoint:], sigs, folder, meta_dir, xyz_dest,
                              revision, failures))
    bad = active[0]
    if status != 124:  # Timeout is transient, so do not permanently suppress retries.
        failures[bad.name] = {'signature': sigs[bad.name],
                              'reason': f'sphere analysis failed (exit code {status}); see terminal output'}
        log(f'    [invalid] {bad.name}: failed physical/format check, skipped until changed')
    else:
        log(f'    [defer] {bad.name}: subprocess timed out; retry next scan')
    return 0


def existing_output_steps(path):
    try:
        with path.open('r', encoding='utf-8-sig') as f:
            header = f.readline().split()
            pos = header.index('timestep')
            return {int(line.split()[pos]) for line in f if line.strip()}
    except (OSError, ValueError, IndexError):
        return set()


def complete_cache(folder, revision, files, meta_dir, xyz_dir):
    completed = []
    for src, sig in files:
        metadata = read_json(meta_dir / (src.stem + '.json'))
        if not metadata or metadata.get('revision') != revision or metadata.get('signature') != sig:
            continue
        dat_path = meta_dir / str(metadata.get('dat', ''))
        xyz_path = xyz_dir / str(metadata.get('xyz', ''))
        if dat_path.is_file() and xyz_path.is_file():
            completed.append(metadata)
    return sorted(completed, key=lambda item: item['timestep'])


def publish(folder, records, meta_dir, cache_root, force=False):
    if not records:
        return False
    output = folder / 'results'
    output.mkdir(exist_ok=True)
    current = [[r['timestep'], r['signature']['mtime_ns'], r['signature']['size'],
                r['revision']] for r in records]
    fingerprint = hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()
    pub_state = read_json(cache_root / 'published.json')
    result_file = output / 'defect_results.dat'
    faces_file = output / 'delaunay.dat'
    if (pub_state.get('fingerprint') == fingerprint
            and result_file.is_file() and faces_file.is_file()):
        return False
    old_steps = existing_output_steps(result_file)
    new_steps = {r['timestep'] for r in records}
    # Never discard an existing result frame merely because its cache is not rebuilt yet.
    if old_steps - new_steps:
        log(f'  [protect] existing result has {len(old_steps-new_steps)} older timestep(s) '
            'not yet recached; preserve original outputs until migration is complete')
        return False
    previous_set = set(pub_state.get('steps', []))
    n_changed = len(new_steps - previous_set) + len(previous_set - new_steps)
    last = pub_state.get('timestamp', 0)
    if (not force and result_file.is_file() and faces_file.is_file()
            and n_changed < PUBLISH_EVERY_NEW
            and time.time() - last < PUBLISH_INTERVAL_SECONDS):
        return False
    # Write to temporary *complete* files before replacing old published files.
    temp_dir = Path(tempfile.mkdtemp(prefix='.sphere_publish_', dir=str(output)))
    try:
        charges = {-1}  # same original script's -1/2 output policy
        for meta in records:
            for label in meta['record']['counts']:
                if label.endswith('/2'):
                    numerator = int(label[:-2])
                    charges.add(numerator)
                else:
                    charges.add(2 * int(label))
        charges = sorted(charges, key=lambda q: (-abs(q), q < 0))
        label = lambda q: str(q//2) if q % 2 == 0 else f'{q:+d}/2'
        columns = [label(q) for q in charges]
        # Original header and exact numeric strings from its batch output.
        with (temp_dir / 'defect_results.dat').open('w', encoding='utf-8', newline='\n') as f:
            f.write('\t'.join(['timestep', *columns, 'net_charge', 'total_defects']) + '\n')
            for meta in records:
                row = meta['record']
                f.write('\t'.join([str(meta['timestep'])] +
                                  [str(row['counts'].get(k, 0)) for k in columns] +
                                  [row['net_charge'], str(row['total'])]) + '\n')
        with (temp_dir / 'delaunay.dat').open('wb') as out:
            out.write(b'# timestep voronoi_x voronoi_y voronoi_z triangle_idx1 '
                      b'triangle_idx2 triangle_idx3 delta_theta charge\n')
            for meta in records:
                with (meta_dir / meta['dat']).open('rb') as src:
                    shutil.copyfileobj(src, out, length=1 << 20)
        os.replace(temp_dir / 'defect_results.dat', result_file)
        os.replace(temp_dir / 'delaunay.dat', faces_file)
        save_json(cache_root / 'published.json', {'fingerprint': fingerprint,
                  'steps': sorted(new_steps), 'timestamp': time.time()})
        log(f'  [publish] {len(records)} frames => results/defect_results.dat, '
            'results/delaunay.dat')
        return True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def average_existing(folder):
    if not DO_AVERAGE or not AVERAGE.is_file():
        return
    source = folder/'results'/'defect_results.dat'
    if not source.is_file():
        return
    steps = sorted(existing_output_steps(source))
    if len(steps) < 4 or len(set(b-a for a, b in zip(steps, steps[1:]))) != 1:
        log('  [average] skipped (fewer than 4 frames or non-uniform sampling interval)')
        return
    # Call original average_defects.py main(input_file,output_dir), not newly added CLI.
    code = ("import importlib.util,sys; "
            "p=sys.argv[1]; s=importlib.util.spec_from_file_location('original_average',p); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
            "m.main(input_file=sys.argv[2],output_dir=sys.argv[3])")
    result = subprocess.run([PYTHON, '-c', code, str(AVERAGE), str(source),
                             str(source.parent)], cwd=str(folder), check=False)
    if result.returncode:
        log(f'  [average] old program returned {result.returncode}; defect DAT remains intact')


def folder_key(path):
    m = re.fullmatch(r'F_([-+]?\d+(?:\.\d+)?)', path.name)
    return (0, float(m.group(1))) if m else (1, path.name)


def process_folder(folder, revision, iteration):
    cache_root = folder/'.sphere_compatible_cache'
    meta_dir = cache_root/'frames'
    meta_dir.mkdir(parents=True, exist_ok=True)
    xyz_dir = folder/'defect_out'
    xyz_dir.mkdir(parents=True, exist_ok=True)
    failure_path = cache_root/'failed_frames.json'
    failures = read_json(failure_path)
    if not isinstance(failures, dict):
        failures = {}
    raw, pending, converted = 0, 0, 0
    known = []
    jobs = []
    all_paths = sorted((p for p in folder.glob('out-*.xyz') if p.is_file()),
                       key=lambda p: timestep(p) if timestep(p) is not None else -1)
    for path in all_paths:
        try:
            sig = signature(path)
            if not mature(sig):
                pending += 1
                continue
            kind = xyz_kind(path)
            if kind == 'raw':
                raw += 1  # never pass old converted file through conversion again
                continue
            if kind != 'converted' or timestep(path) is None:
                pending += 1
                continue
            converted += 1
            known.append((path, sig))
            memo = read_json(meta_dir/(path.stem + '.json'))
            cached = (memo.get('revision') == revision and memo.get('signature') == sig
                      and (meta_dir/str(memo.get('dat', ''))).is_file()
                      and (xyz_dir/str(memo.get('xyz', ''))).is_file())
            if not cached and failures.get(path.name, {}).get('signature') != sig:
                jobs.append(path)
        except (OSError, ValueError) as exc:
            pending += 1
            log(f'  [pending] {path.name}: {exc}')
    log(f'\n[round {iteration}] {folder.name}: all={len(all_paths)}, converted={converted}, '
        f'raw-skipped={raw}, pending={pending}, new-to-compute={len(jobs)}')
    if raw:
        log('  [note] raw LAMMPS dump frames are SKIPPED; already-converted files '
            'are used directly, converter never called')
    sigs = {path.name: sig for path, sig in known}
    processed = 0
    quota = len(jobs) if RUN_ONCE else min(len(jobs), MAX_NEW_PER_FOLDER)
    for offset in range(0, quota, BATCH_SIZE):
        group = jobs[offset:offset+BATCH_SIZE]
        processed += process_group(group, sigs, folder, meta_dir, xyz_dir,
                                   revision, failures)
    save_json(failure_path, failures)
    records = complete_cache(folder, revision, known, meta_dir, xyz_dir)
    published = publish(folder, records, meta_dir, cache_root, force=RUN_ONCE)
    if published:
        average_existing(folder)
    log(f'  [status] cache={len(records)}, new={processed}, '
        f'invalid={len(failures)}, still-to-process={max(0,len(jobs)-quota)}')


def verify_dependencies():
    # Only check the parameters that EXIST on the original Python source.
    cmd = [PYTHON, str(SPHERE), '--help']
    check = subprocess.run(cmd, cwd=str(ROOT), capture_output=True,
                           text=True, errors='replace', timeout=90, check=False)
    flags = ('--input-dir', '--pattern', '--output', '--xyz-output',
             '--chain-length', '--workers', '--timeout')
    if check.returncode != 0:
        raise SystemExit('sphere_nematic_parallel.py --help failed:\n'+check.stderr[-4000:])
    unsupported = [f for f in flags if f not in check.stdout]
    if unsupported:
        raise SystemExit('Original sphere_nematic_parallel.py lacks flags: '+', '.join(unsupported))
    return hashlib.sha256(SPHERE.read_bytes() +
                          f'|chain_length={CHAIN_LENGTH}|input=converted_xyz_4cols'.encode()).hexdigest()


# Protect against two copies of run.sh writing the same results.
lock_file = (ROOT/'.run_compatible.lock').open('a+')
try:
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit('Another compatible run.sh is active in this directory. Stop it first.')
revision = verify_dependencies()
log(f'[run compatible v4] ROOT={ROOT}\n'
    f'  original sphere source={SPHERE.name}, revision={revision[:12]}\n'
    f'  DO NOT call convert_lammps_to_bd.py; process only preconverted XYZ\n'
    f'  CHAIN_LENGTH={CHAIN_LENGTH}, DEFECT_WORKERS={WORKERS}, '
    f'BATCH_SIZE={BATCH_SIZE}, MAX_NEW_PER_FOLDER={MAX_NEW_PER_FOLDER}, '
    f'STABLE_SECONDS={STABLE_SECONDS}, RUN_ONCE={RUN_ONCE}, ONLY_F={ONLY_F or "all"}')
try:
    round_num = 0
    while True:
        round_num += 1
        folders = sorted((p for p in ROOT.iterdir()
                          if p.is_dir() and p.name.startswith('F_')), key=folder_key)
        if ONLY_F:
            folders = [p for p in folders if p.name == ONLY_F]
        if not folders:
            log('[info] No F_* folders match')
        for folder in folders:
            try:
                process_folder(folder, revision, round_num)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                log(f'[error] {folder.name}: {type(exc).__name__}: {exc}; continue next folder')
        if RUN_ONCE:
            log('[done] Single sweep complete')
            break
        log(f'[poll] scan completed; next pass in {SCAN_INTERVAL_SECONDS:g}s; Ctrl+C to stop')
        time.sleep(SCAN_INTERVAL_SECONDS)
except KeyboardInterrupt:
    log('\n[exit] Interrupted cleanly. Original out-*.xyz files were NEVER modified.')
finally:
    lock_file.close()
PY
