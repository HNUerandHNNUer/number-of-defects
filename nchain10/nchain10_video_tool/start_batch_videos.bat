@echo off
setlocal
chcp 65001 >nul
REM Edit this only if your PyMOL command is not available in PATH.
REM Example: set "PYMOL_EXE=C:\path\to\PyMOLWin.exe"
set "PYMOL_EXE=pymol"
if exist "D:\Anaconda3\Scripts\pymol.EXE" set "PYMOL_EXE=D:\Anaconda3\Scripts\pymol.EXE"
set "ROOT=E:\1\7.9.2025\3000\phi_0.7\number of defects\new\nchain10"
set "SCRIPT_DIR=%~dp0"

py -3 "%SCRIPT_DIR%batch_defect_videos.py" --root "%ROOT%" --pymol "%PYMOL_EXE%" --format avi --fps 12 --width 800 --height 800 %*
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Processing failed or incomplete. See errors above.
echo Press any key to close this window.
pause >nul
exit /b %RC%
