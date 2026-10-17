#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-command batch renderer + video encoder for spherical defect XYZ trajectories.

1. Finds ROOT/F_*/**/defect_out/defect_out-<step>.xyz
2. Starts PyMOL in batch mode to render PNG frames using render_defect_pymol.py
3. Stitches the PNGs with OpenCV and saves ROOT/video/<F-value>.avi (or .mp4)

Requirements in THIS Python environment: pip install opencv-python numpy
PyMOL is launched separately and need not be importable from this Python.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

DEFAULT_ROOT = r"E:\1\7.9.2025\3000\phi_0.7\number of defects\new\nchain150"
F_PATTERN = re.compile(r"^F_(\d+(?:\.\d+)?)(?:_.*)?$", re.IGNORECASE)
XYZ_PATTERN = re.compile(r"^defect_out-(\d+)\.xyz$", re.IGNORECASE)


def discover(root):
    jobs = []
    for folder in root.iterdir():
        if not folder.is_dir():
            continue
        match = F_PATTERN.fullmatch(folder.name)
        if not match:
            continue
        value = match.group(1)
        for defect_dir in folder.rglob("defect_out"):
            if not defect_dir.is_dir():
                continue
            pairs = []
            for file in defect_dir.iterdir():
                if file.is_file():
                    step_match = XYZ_PATTERN.fullmatch(file.name)
                    if step_match:
                        pairs.append((int(step_match.group(1)), file))
            pairs.sort(key=lambda pair: (pair[0], pair[1].name))
            if not pairs:
                print("[SKIP] Empty defect_out: " + str(defect_dir), flush=True)
                continue
            nums = [step for step, _ in pairs]
            if len(nums) != len(set(nums)):
                raise ValueError("Duplicate timesteps in " + str(defect_dir))
            jobs.append({"value": value, "folder": folder, "source": defect_dir,
                         "files": pairs})
    jobs.sort(key=lambda job: (float(job["value"]), str(job["folder"]).lower(), str(job["source"]).lower()))
    return jobs


def safe_name(name):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")


def assign_names(jobs, extension):
    # Duplicate F values cannot all have the same filename. Give every duplicate
    # an informative suffix rather than silently overwriting a simulation.
    freq = Counter(job["value"] for job in jobs)
    seen = set()
    for job in jobs:
        prefix = job["value"]
        if freq[prefix] > 1:
            nested = job["source"].relative_to(job["folder"])
            part = "_".join(nested.parts[:-1])
            suffix = job["folder"].name + ("__" + part if part else "")
            filename = prefix + "__" + safe_name(suffix) + extension
        else:
            filename = prefix + extension
        if filename.lower() in seen:
            raise ValueError("Output name conflict: " + filename)
        job["filename"] = filename
        seen.add(filename.lower())


def imread_win(path, cv2, np):
    # np.fromfile + imdecode handles non-ASCII Windows paths more reliably.
    image_data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(image_data, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError("Unreadable PNG: " + str(path))
    if len(image.shape) == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        bgr, alpha = image[:, :, :3].astype(np.float32), image[:, :, 3:4].astype(np.float32) / 255
        return np.clip(bgr * alpha + 255 * (1 - alpha), 0, 255).astype(np.uint8)
    return image


def encode(frames, dest, fps, width, height):
    try:
        import cv2
        import numpy as np
    except ImportError as error:
        raise RuntimeError("Install dependencies: py -m pip install opencv-python numpy") from error
    extension = dest.suffix.lower()
    choices = [("mp4v",)] if extension == ".mp4" else [("XVID",), ("MJPG",)]
    writer = None
    temp = dest.with_name("." + dest.stem + ".rendering" + extension)
    temp.unlink(missing_ok=True)
    try:
        for (codec,) in choices:
            trial = cv2.VideoWriter(str(temp), cv2.VideoWriter_fourcc(*codec), fps, (width, height))
            if trial.isOpened():
                writer = trial
                print("[CODEC] " + codec, flush=True)
                break
            trial.release()
        if writer is None:
            raise RuntimeError("No working OpenCV codec for " + extension + ". Try .avi or check codecs.")
        for i, image_path in enumerate(frames, 1):
            image = imread_win(image_path, cv2, np)
            if (image.shape[1], image.shape[0]) != (width, height):
                # A different-sized image should never silently change the movie.
                raise RuntimeError("PNG size mismatch: " + str(image_path) + " : " + str(image.shape))
            writer.write(image)
            if i == 1 or i % 50 == 0 or i == len(frames):
                print("[ENCODE] %d/%d" % (i, len(frames)), flush=True)
        writer.release()
        writer = None
        if not temp.is_file() or temp.stat().st_size == 0:
            raise RuntimeError("Output video is missing or empty: " + str(temp))
        os.replace(temp, dest)
    finally:
        if writer is not None:
            writer.release()
        temp.unlink(missing_ok=True)


@contextmanager
def frame_workspace(output_dir, folder, keep):
    if keep:
        work = output_dir / "png_frames" / safe_name(folder)
        work.mkdir(parents=True, exist_ok=True)
        yield work
    else:
        with tempfile.TemporaryDirectory(prefix=".defect_png_", dir=str(output_dir)) as temp:
            yield Path(temp)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Batch PyMOL XYZ renderer + OpenCV video encoder")
    p.add_argument("--root", default=DEFAULT_ROOT, help="nchain150 directory containing F_* folders")
    p.add_argument("--pymol", default="pymol", help="PyMOL CLI executable name or full .exe path")
    p.add_argument("--format", choices=("avi", "mp4"), default="avi")
    p.add_argument("--fps", type=float, default=12)
    p.add_argument("--width", type=int, default=800)
    p.add_argument("--height", type=int, default=800)
    p.add_argument("--stride", type=int, default=1, help="Use every nth XYZ frame (default: all)")
    p.add_argument("--max-frames", type=int, default=0, help="0: all selected frames; e.g. 3 for trial run")
    p.add_argument("--only", default=None, help="Only a specific F_* directory, e.g. F_0.1_gpu3")
    p.add_argument("--beads-per-chain", type=int, default=30)
    p.add_argument("--ray", type=int, choices=(0, 1), default=1,
                   help="1=ray tracing (headless safe); 0=OpenGL (may require a GUI)")
    p.add_argument("--boundary", action="store_true", help="Draw box boundary if BoxSize exists")
    p.add_argument("--overwrite", action="store_true", help="Replace existing videos")
    p.add_argument("--keep-png", action="store_true", help="Keep rendered PNG under video/png_frames")
    p.add_argument("--dry-run", action="store_true", help="Only list tasks and expected filenames")
    args = p.parse_args(argv)
    if args.fps <= 0 or args.width <= 0 or args.height <= 0 or args.stride < 1 or args.max_frames < 0:
        p.error("Invalid fps/size/stride/max-frames")
    if args.width % 2 or args.height % 2:
        p.error("Please use even width and height for video codecs")
    if args.beads_per_chain < 2:
        p.error("beads-per-chain must be >= 2")
    return args


def main(argv=None):
    args = parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError("Root directory does not exist: " + str(root))
    script = Path(__file__).resolve().with_name("render_defect_pymol.py")
    if not script.is_file() and not args.dry_run:
        raise FileNotFoundError("Place render_defect_pymol.py beside this script: " + str(script))
    jobs = discover(root)
    if args.only:
        jobs = [job for job in jobs if job["folder"].name.lower() == args.only.lower()]
    if not jobs:
        raise RuntimeError("No matching F_*/**/defect_out/defect_out-<number>.xyz trajectories were found")
    assign_names(jobs, "." + args.format)
    output_dir = root / "video"
    print("ROOT:", root, "\nVIDEO:", output_dir, "\nFOUND:", len(jobs), "trajectories", flush=True)
    for job in jobs:
        selected = job["files"][::args.stride]
        if args.max_frames:
            selected = selected[:args.max_frames]
        job["selected"] = selected
        print("[PLAN] %-35s %4d/%-4d -> %s" % (str(job["source"].relative_to(root)),
                                                     len(selected), len(job["files"]), job["filename"]), flush=True)
    if args.dry_run:
        print("Dry run only. No files created.")
        return 0
    executable = shutil.which(args.pymol) or (str(Path(args.pymol)) if Path(args.pymol).is_file() else None)
    if executable is None:
        raise FileNotFoundError("Cannot find PyMOL executable. Supply --pymol with its full path or add pymol to PATH.")
    output_dir.mkdir(parents=True, exist_ok=True)
    succeeded, skipped, failed = [], [], []
    for index, job in enumerate(jobs, 1):
        dest = output_dir / job["filename"]
        print("\n========= %d/%d %s =========" % (index, len(jobs), job["source"]), flush=True)
        if dest.exists() and not args.overwrite:
            print("[SKIP] Video already exists (use --overwrite to replace):", dest, flush=True)
            skipped.append(str(dest))
            continue
        try:
            workspace_name = job["folder"].name + "__" + str(job["source"].relative_to(job["folder"])).replace("\\", "_").replace("/", "_")
            with frame_workspace(output_dir, workspace_name, args.keep_png) as work:
                manifest = []
                for timestep, xyz_path in job["selected"]:
                    png_path = work / ("defect_%010d.png" % timestep)
                    manifest.append({"source": str(xyz_path), "target": str(png_path)})
                job_file = work / "render_job.json"
                job_file.write_text(json.dumps({"frames": manifest,
                                                "width": args.width, "height": args.height,
                                                "beads_per_chain": args.beads_per_chain,
                                                "boundary": args.boundary, "ray": args.ray},
                                               ensure_ascii=False, indent=2), encoding="utf-8")
                env = os.environ.copy()
                env["DEFECT_VIDEO_JOB"] = str(job_file)
                command = [executable, "-cq", "-r", str(script)]
                print("[PYMOL]", subprocess.list2cmdline(command), flush=True)
                result = subprocess.run(command, env=env, check=False)
                if result.returncode != 0:
                    raise RuntimeError("PyMOL rendering failed (return code %d)" % result.returncode)
                pngs = [Path(item["target"]) for item in manifest]
                missing = [path for path in pngs if not path.is_file() or path.stat().st_size == 0]
                if missing:
                    raise RuntimeError("PyMOL did not produce %d/%d images; first missing: %s" %
                                       (len(missing), len(pngs), missing[0]))
                encode(pngs, dest, args.fps, args.width, args.height)
            print("[SUCCESS]", dest, flush=True)
            succeeded.append(str(dest))
        except Exception as exc:
            failed.append((str(job["source"]), str(exc)))
            print("[FAILED]", repr(exc), flush=True)
    print("\n========== SUMMARY ==========")
    print("Succeeded:", len(succeeded), "Skipped:", len(skipped), "Failed:", len(failed))
    for source, reason in failed:
        print("[FAILED]", source, "->", reason)
    print("VIDEO:", output_dir)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
