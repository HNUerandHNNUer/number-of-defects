# number-of-defects

LAMMPS 模拟中**缺陷数（number of defects）**随链长变化的源文件与统计结果汇总。

- 体系参数：`phi = 0.7`
- 变量：链长 `nchain = 10, 30, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500`
- 每个链长下扫描多个力参数 `F`（如 `F_0.003`、`F_0.1`、`F_0.55` …），部分参数在不同 CPU/编译版本下重复运行

## 目录结构

```
nchain<N>/
├── <F>.txt                  # 该力参数下的缺陷数统计结果（每行一个统计量）
├── F_<F>/                   # 单次运行的 LAMMPS 工作目录
│   ├── *.in / *.lammps      # 输入脚本
│   ├── results/*.dat        # 逐帧缺陷数原始结果
│   └── ...                  # 日志、配置等文本文件
└── (部分目录) fortran_openmp_complete/ 、cpu*/   # 修改版 LAMMPS 源码与编译配置
```

仓库根目录另含分析脚本：`average_defects.py`、`convert_lammps_to_bd.py`、
`bd.f90` / `bd_read.f90` / `module.f90`、`cluster_*.py`、`run.sh`、
`sphere_nematic_parallel_large_v4.py`，以及集群使用说明 `CLUSTER_README.md`。

## 数据清单

| 目录 | 文件数 | 体积 (MB) |
|---|---:|---:|
| nchain10 | 398 | 63.8 |
| nchain30 | 108 | 14.8 |
| nchain50 | 128 | 20.9 |
| nchain100 | 10,022 | 288.3 |
| nchain150 | 181 | 33.7 |
| nchain200 | 200 | 40.4 |
| nchain250 | 217 | 67.9 |
| nchain300 | 208 | 61.4 |
| nchain350 | 210 | 55.5 |
| nchain400 | 226 | 65.4 |
| nchain450 | 183 | 70.0 |
| nchain500 | 157 | 47.5 |
| **合计** | **12,238** | **829.6** |

机器可读版本见 [`data_inventory.csv`](data_inventory.csv)。

## 统计口径

各 `<F>.txt` 文件头部记录了统计方式，例如：

```
# status: 固定丢弃前25%帧，仅统计后75%帧
# 固定统计时间步: 25000000 — 100000000
# 总帧数: 1001；舍弃前25%: 250；统计后75%: 751
# mean为分别四舍五入后的整数；raw_mean保留原始均值
```

## 未纳入本仓库的内容

以下为体积过大的原始数据，未上传（完整数据约 **516 GB / 105 万文件**）：

| 类型 | 文件数 | 体积 |
|---|---:|---:|
| `.xyz` 轨迹 | 1,014,409 | 365.8 GB |
| `.avi` 视频 | 188 | 111.9 GB |
| `.png` 图片 | 18,387 | 6.2 GB |
| `.lammps` 大日志（>5 MB） | 96 | 0.8 GB |
| 超大单文件（>20 MB） | 5 | 17.8 GB |

如需原始轨迹/视频，可另行提供（网盘或对象存储）。

## 使用建议

```bash
# 汇总各链长的缺陷数（示例，按需修改路径）
python average_defects.py
```

- 逐帧数据：`nchain<N>/F_<F>/results/defect_results.dat`
- 链长对比：读取各 `nchain<N>/<F>.txt` 的 `mean` / `raw_mean` 列
