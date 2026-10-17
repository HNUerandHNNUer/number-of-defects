# -*- coding: utf-8 -*-
"""PyMOL batch renderer. Called by batch_defect_videos.py, not directly.

Uses the particle/defect sizes and colors of the supplied load.py:
  type 1: gradient blue-purple-magenta, every 30th bead white
  type 2: yellow; 3: red; 4: blue; 5: green
All images use one fixed camera per simulation, white opaque background.
"""
import json
import os
import re
import sys
import traceback
from pathlib import Path

from pymol import cmd
from pymol.cgo import BEGIN, END, LINES, COLOR, VERTEX


def get_box(xyz_path):
    with open(xyz_path, "r", encoding="utf-8-sig") as f:
        count = f.readline().strip()
        header = f.readline().strip()
    if not count.isdigit() or int(count) < 1:
        raise ValueError("Invalid XYZ particle count: " + str(xyz_path))
    match = re.search(r"BoxSize:\s*([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)", header)
    return [float(x) for x in match.groups()] if match else None


def draw_boundary(box):
    if box is None:
        return
    bx, by, bz = (v / 2.0 for v in box)
    corners = [(x, y, z) for x in (-bx, bx)
              for y in (-by, by) for z in (-bz, bz)]
    obj = [BEGIN, LINES, COLOR, 0.10, 0.10, 0.10]
    for i, a in enumerate(corners):
        for j, b in enumerate(corners):
            if j > i and sum(a[k] != b[k] for k in range(3)) == 1:
                obj.extend([VERTEX, *a, VERTEX, *b])
    obj.append(END)
    cmd.load_cgo(obj, "boundary_box")


def style_frame(beads_per_chain, boundary_box):
    cmd.hide("everything", "all")
    cmd.show("spheres", "all")
    cmd.alter("all", "vdw=0.45")
    for atom_type in (2, 3, 4, 5):
        cmd.alter("name %d" % atom_type, "vdw=0.6")

    colors = {
        2: ("defect_yellow_safe", [0.90, 0.80, 0.15]),
        3: ("defect_red_safe", [0.85, 0.15, 0.15]),
        4: ("defect_blue_safe", [0.15, 0.40, 0.85]),
        5: ("defect_green_safe", [0.15, 0.75, 0.30]),
    }
    for atom_type, (name, rgb) in colors.items():
        cmd.set_color(name, rgb)
        cmd.color(name, "name %d" % atom_type)

    # Match the source script's per-chain gradient and white end bead.
    base_atoms = cmd.get_model("name 1").atom
    if base_atoms:
        cmd.color("purple", "name 1")
        b_by_index = {
            atom.index: (100 if (position + 1) % beads_per_chain == 0
                         else position // beads_per_chain)
            for position, atom in enumerate(base_atoms)
        }
        cmd.alter("name 1", "b = b_by_index[index]", space={"b_by_index": b_by_index})
        cmd.spectrum("b", "blue_purple_magenta", "name 1", minimum=0, maximum=99)
        cmd.color("white", "name 1 and b=100")
        cmd.set("sphere_transparency", 0.1, "name 1")

    cmd.rebuild()
    if boundary_box is not None:
        draw_boundary(boundary_box)


def render(job):
    width, height = int(job["width"]), int(job["height"])
    ray = int(job.get("ray", 1))
    bead_count = int(job.get("beads_per_chain", 30))
    if bead_count < 2:
        raise ValueError("beads_per_chain must be >= 2")
    cmd.bg_color("white")
    cmd.set("ray_opaque_background", 1)
    cmd.set("opaque_background", 1)
    cmd.set("orthoscopic", 1)
    cmd.set("light_count", 1)
    cmd.set("stick_nub", 0)
    cmd.set("connect_mode", 1)
    cmd.set("auto_zoom", 0)  # Keep physical axes consistent across frames and F conditions.

    camera = None
    frames = job["frames"]
    for i, frame in enumerate(frames, start=1):
        source = Path(frame["source"])
        target = Path(frame["target"])
        target.parent.mkdir(parents=True, exist_ok=True)
        cmd.delete("all")
        cmd.load(str(source), "defect_particles", format="xyz")
        box = get_box(source) if job.get("boundary", False) else None
        style_frame(bead_count, box)

        if camera is None:
            # Zoom only; avoid orient(), which rotates nearly spherical data
            # differently for different activity conditions.
            cmd.zoom("defect_particles", buffer=3.0)
            camera = cmd.get_view()
        else:
            cmd.set_view(camera)

        cmd.png(str(target), width=width, height=height, dpi=300, ray=ray, quiet=1)
        if not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError("PyMOL did not create the expected PNG: " + str(target))
        if i == 1 or i % 25 == 0 or i == len(frames):
            print("[PyMOL] %d/%d %s" % (i, len(frames), source.name), flush=True)


def main():
    job_file = os.environ.get("DEFECT_VIDEO_JOB")
    if not job_file:
        raise RuntimeError("DEFECT_VIDEO_JOB environment variable is missing. Run batch_defect_videos.py instead.")
    with open(job_file, "r", encoding="utf-8") as f:
        job = json.load(f)
    render(job)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
        cmd.quit(1)
        raise
    cmd.quit(0)
