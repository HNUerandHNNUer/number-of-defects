球面活性向列缺陷：Windows 批量 XYZ -> PyMOL PNG -> AVI/MP4
======================================================

文件：
  batch_defect_videos.py     Windows 主控制程序（通过 Windows Python 执行）
  render_defect_pymol.py    PyMOL 渲染程序（由主程序启动 PyMOL 自动执行）
  start_batch_videos.bat    双击可运行的 Windows 启动器

默认根目录：
E:\1\7.9.2025\3000\phi_0.7\number of defects\new\nchain50

默认输出目录：
<根目录>\video\

说明：
1. 仅识别 F_<数值>[_附加说明] 文件夹与 defect_out/defect_out-<整数>.xyz 单帧文件。
2. 支持 defect_out 直接在 F_*/ 下，也支持 F_*/1/defect_out 等额外嵌套。
3. 文件时间步从小到大排列，不强行推断或补造缺失帧。
4. 唯一活性力数值生成 0.1.avi；数值重复时自动加来源后缀以避免覆盖。
5. 原文件不修改。中间 PNG 默认编码成功后自动清理。
6. .video 不是标准视频格式：请选 .avi 或 .mp4。
7. PyMOL 默认使用 ray=1 (光线追踪)；1001 帧可能耗时较长。
8. 默认球面链长度30、PNG尺寸800×800、帧率12。

首次安装：
  py -3 -m pip install opencv-python numpy
确认 PyMOL 命令：
  where.exe pymol
如果 where.exe 找不到，可给 --pymol 参数填实际 PyMOL 可执行文件的完整路径。

将三个文件放在同一个文件夹，可在 PowerShell 中运行：
  py -3 .\batch_defect_videos.py --dry-run
  py -3 .\batch_defect_videos.py --only F_0.1_gpu3 --max-frames 3
  py -3 .\batch_defect_videos.py

更多选项：
  --pymol "C:\...\PyMOLWin.exe"  指定 PyMOL 可执行文件
  --root "D:\other_root"       更换数据根目录
  --format mp4               输出 MP4 而不是 AVI
  --fps 20                   FPS=20
  --width 1280 --height 1280 更高分辨率
  --stride 5                 每五个 XYZ 帧渲染一张图（加速）
  --only F_0.1_gpu3           仅处理一个工况
  --max-frames 3             仅渲染前三个选中帧（测试）
  --overwrite                覆盖已有视频
  --keep-png                 保留中间 PNG
  --boundary                 在存在 BoxSize 时画出边界框
  --ray 0                    不做 ray trace（命令行无 GUI 时可能不可用）

需要完整重新生成已有测试视频时，请加 --overwrite。

验证说明：已使用模拟 XYZ 目录、模拟 PNG 渲染进程完成主程序端到端测试，
并验证编码的 AVI 可以由 OpenCV 读取；目前环境没有本机 Windows PyMOL，
PyMOL 渲染必须在用户自己的 Windows/PyMOL 安装上实测。
