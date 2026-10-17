# 12 台服务器的任务队列

这个工具适合大量**彼此独立**的计算任务。Windows 电脑负责排队、选机器、上传输入、启动计算和取回结果；任务在服务器上独立运行。它不修改现有 Slurm 服务，也不停止已有计算。

## 第一次使用

在 PowerShell 中进入本目录，执行：

```powershell
python cluster_queue.py nodes
```

已为这 12 台服务器安装专用 SSH 公钥；私钥位于当前 Windows 用户的 `~/.ssh/id_ed25519_codex_cluster`。命令无需再输入密码，会显示各节点当前剩余内存、磁盘空间、CPU 负载和 GPU 是否忙碌。

## 提交任务

先建一个**只含输入和程序**的文件夹。运行期间产生的数据不要提前放进去；整个输入文件夹会上传到选中的服务器。命令在该文件夹中执行。

以本工作区 `nchain50\F_9_cpu2\bd.in` 为例，它读取同目录的 `polymer.data`。先在本目录的 PowerShell 中准备一个干净的输入文件夹：

```powershell
$jobDir = Join-Path (Get-Location) 'cluster_inputs\bd_case01'
New-Item -ItemType Directory -Force -Path $jobDir | Out-Null
Copy-Item -LiteralPath '.\nchain50\F_9_cpu2\bd.in', '.\nchain50\F_9_cpu2\polymer.data' -Destination $jobDir
python .\cluster_queue.py submit $jobDir 'lmp -in bd.in' --kind cpu --cores 1 --memory-gib 8
```

这份 `bd.in` 包含 10,000,000 步预运行和 100,000,000 步生产段，上面的提交命令会启动完整计算。它使用临时文件生成随机种子；实际演示发现直接用 `mpirun -np 4` 会发生多进程读取冲突，因此这里先用单进程。任务编号会在提交后显示。每个独立计算应使用自己的输入文件夹，避免把旧的 `log.lammps`、轨迹或 restart 文件一起上传。

```powershell
python cluster_queue.py submit "D:\jobs\case01" "mpirun -np 4 lmp -in bd.in" --kind cpu --cores 4 --memory-gib 8
python cluster_queue.py submit "D:\jobs\case02" "bash run.sh" --kind gpu --cores 4 --memory-gib 16
```

`command` 必须适用于最终选中的每一台同类节点。若各机的软件路径不同，请在输入文件夹的 `run.sh` 中自行选择可用的可执行文件。GPU 任务目前只要求有一张空闲 NVIDIA GPU；显卡型号并不相同，显存要求高的任务需要进一步增加型号筛选后再提交。

调度循环已经作为 Windows 计划任务 `CodexClusterQueue` 启动，并会在当前用户登录时自动启动。提交后通常在约一分钟内检查新任务。若要手动重启或停止它：

```powershell
Start-ScheduledTask -TaskName CodexClusterQueue
Stop-ScheduledTask -TaskName CodexClusterQueue
```

Windows 电脑需要保持开机、联网且不睡眠。已经启动的远端任务在调度程序暂停时仍会继续运行；调度程序恢复后会继续检查结果和派发等待中的任务。后台日志写入本目录 `cluster_service.log`。

查看队列：

```powershell
python cluster_queue.py status
```

完成的结果会**自动复制**到本目录的 `cluster_results\任务编号` 中，包括 `log.lammps`、轨迹、restart 文件、输入文件和 `cluster.stdout.log`/`cluster.stderr.log`。自动复制只在任务结束后开始；运行期间的文件留在计算节点上。`done` 表示程序退出码为 0；`failed` 表示程序报错，可查看其中的 `cluster.stderr.log`；`copy_error` 表示远端计算已经结束，但结果还没完整复制到本机，调度循环会重试。远端数据保留在 `/home/user/cluster_jobs/任务编号`，工具不会自动删除它。大任务在本机还需留出足够磁盘空间接收结果。

## 当前分配规则

- CPU 任务只去 CPU1–CPU6；GPU 任务只去 GPU1–GPU6。
- 同一时刻，每台服务器最多启动一个**由此工具管理**的新任务。
- 如果 CPU 负载超过逻辑线程数的 60%、GPU 利用率达到 15% 或显存占用达到 1 GiB，则暂缓向该节点派发。
- 派发前至少保留 4 GiB 可用内存、20 GiB 远端磁盘空间；取回结果前至少保留 5 GiB 本机空间。
- 这些是保守的快照判断。现有任务若在检查后突然占满资源，工具无法替它们预留资源。

本方案通过截图中的公网映射 SSH 入口工作，绕过了两组服务器之间尚未打通的内网。它是独立任务队列；如果今后需要集群用户管理、优先级、资源抢占或跨节点 MPI，再修好内网并统一部署 Slurm。
