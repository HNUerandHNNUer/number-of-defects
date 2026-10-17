NCHAIN10 DEFECT XYZ -> VIDEO
============================

Root directory (automatically configured):
E:\1\7.9.2025\3000\phi_0.7\number of defects\new\nchain10

Processing:
- Scan each root/F_* folder, optionally with nested subfolders, for defect_out/defect_out-<numeric_timestep>.xyz.
- Sort frames by the integer timestep, render with PyMOL, encode with OpenCV.
- Save output root/video/<number>.avi; strip suffixes like _cpu1 or _gpu4.
- If multiple trajectories have the same F value, add identifying suffixes to avoid overwriting.
- The original input XYZ files are not modified.

Files:
batch_defect_videos.py    Batch orchestrator, output naming, OpenCV encoding
render_defect_pymol.py    PyMOL headless frame rendering
start_batch_videos.bat   Windows launch shortcut (uses py -3)

Install (outside PyMOL Python, from PowerShell):
py -3 -m pip install numpy opencv-python

FIRST: dry run (in this extracted folder)
py -3 .\batch_defect_videos.py --dry-run

TEST 3 FRAMES ONLY:
py -3 .\batch_defect_videos.py --only F_0.1_cpu1 --max-frames 3

FULL BATCH (REPLACE THE 3-FRAME TRIAL VIDEO):
py -3 .\batch_defect_videos.py --overwrite

SMALLER VIDEO / FASTER RENDERING:
py -3 .\batch_defect_videos.py --stride 10 --overwrite

Or double-click start_batch_videos.bat to run the full batch.
Or from cmd.exe:
start_batch_videos.bat --stride 10 --overwrite

Optional command arguments:
--root "E:\...\nchain250"  Process another nchain folder without editing code
--format mp4          Output MP4 if the local OpenCV mp4v codec works
--fps 12              Video frames per second
--width 800 --height 800
--stride 5            Sample every 5th XYZ frame
--max-frames 3        Test with 3 frames
--only F_0.1_cpu1     Render just one matching F_* folder
--pymol "D:\Anaconda3\Scripts\pymol.EXE"  Explicit PyMOL executable
--keep-png            Keep intermediate PNG sequences
--dry-run             Inspect planned jobs, make no outputs
--overwrite           Replace existing videos (needed after trial run)

Important:
1. Video output extension is .avi or .mp4, NOT .video.
2. Processing large 10,001-frame trajectories with ray tracing may take hours.
3. A PyMOL installation is required; the BAT first tries D:\Anaconda3\Scripts\pymol.EXE and otherwise the 'pymol' command.
4. This package's directory and naming functions have been checked with synthetic sample folders; PyMOL cannot be end-to-end tested in this environment.
5. If output from F=0.1 was previously generated as a 3-frame test, rerun with --overwrite to replace it with a full video.
