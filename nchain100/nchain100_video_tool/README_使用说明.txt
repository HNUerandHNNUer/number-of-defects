【nchain100 球面活性向列缺陷视频批处理】

输入根目录：
E:\1\7.9.2025\3000\phi_0.7\number of defects\new\nchain100

自动寻找：F_*\defect_out\defect_out-<时间步>.xyz（包括 F_* 下更深层子目录）
视频输出：<根目录>\video\<F 数值>.avi
例：F_0.1_cpu1 -> video\0.1.avi；F_10_gpu4 -> video\10.avi
重复活性力的不同轨迹会在视频名称添加来源后缀，避免覆盖。

文件：
1. batch_defect_videos.py    批量处理主程序（Python 3 + numpy + opencv-python）
2. render_defect_pymol.py    由主程序启动的 PyMOL 渲染脚本（需安装 PyMOL）
3. start_batch_videos.bat    双击运行入口（需要 Python 的 py -3 命令和 pymol 命令可用）

安装 Python 环境依赖（PowerShell）：
py -3 -m pip install numpy opencv-python

将三个文件一起放在 nchain100\batch_defect_videos_windows 目录中。
在该目录的地址栏输入 powershell 并按 Enter，然后执行：

A. 预览，不生成：
py -3 .\batch_defect_videos.py --dry-run

B. 先测试 F_0.1_cpu1 3 帧（目录不存在时改用实际目录名）：
py -3 .\batch_defect_videos.py --only F_0.1_cpu1 --max-frames 3

C. 全量批处理（默认 800x800, 12 fps, 所有帧, AVI）：
py -3 .\batch_defect_videos.py --overwrite
或双击 start_batch_videos.bat（注意会跳过已有视频；要覆盖测试短视频，请先删掉短视频或者从终端加上 --overwrite）

D. 数据量大可抽帧，例如每 10 帧取 1 帧：
py -3 .\batch_defect_videos.py --stride 10 --overwrite

E. 不删除临时 PNG：
py -3 .\batch_defect_videos.py --keep-png

如 PyMOL 未加入 PATH：
py -3 .\batch_defect_videos.py --pymol "D:\Anaconda3\Scripts\pymol.EXE" --dry-run
正式运行时去掉 --dry-run。

请勿使用 .video 作为输出扩展名，应使用 .avi 或 .mp4。
如果首轮 --max-frames 3 产生短视频，正式全量运行时必须加 --overwrite。
长轨迹光线追踪可能耗时数小时；建议先抽帧或测试 3 帧。
