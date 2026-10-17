#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取 defect_results.dat，只分析按 timestep 排序后的前指定帧数，
然后固定丢弃这部分数据的前 25% 帧，仅使用后 75% 帧进行统计，
输出整数平均缺陷数 ± 原始样本 SD。

使用：
    与 defect_results.dat 放在同一目录，直接运行。

默认：
    分析前 1001 帧。

参数化：
    修改下面的 ANALYSIS_FRAMES 即可改变分析帧数，例如：
        ANALYSIS_FRAMES = 2001
    若设置为 None，则分析 defect_results.dat 中的全部帧。

方法：
    1. 按 timestep 从小到大排序；
    2. 只取前 ANALYSIS_FRAMES 帧；
    3. 在这部分数据中固定丢弃前 25%；
    4. 对剩余 75% 数据计算平均值和样本 SD。

    SD 使用保留区间的全部原始帧及未取整均值，不是 SEM。
    三类平均数分别按四舍五入取整，恰好 .5 时向上取整。
    raw_mean 保留未取整均值。

输出：
    average_defects.txt

依赖：
    numpy
"""

from pathlib import Path
import numpy as np


COLS = ("total_defects", "+1/2", "-1/2")
LABELS = ("total defect", "+1/2 defect", "-1/2 defect")

# ============================================================
# 可调参数
# ============================================================

# 指定只分析按 timestep 排序后的前多少帧。
# 默认前 1001 帧。
# 若设为 None，则使用 defect_results.dat 中的全部帧。
ANALYSIS_FRAMES = 1001

# 固定舍弃所选分析区间的前 25% 帧，只统计后 75%。
DISCARD_FRACTION = 0.25


def rounded_count_mean(values):
    """非负整数计数的均值四舍五入；用整数运算避免 .5 舍入歧义。"""
    n = len(values)
    total = sum(int(value) for value in values)
    return (2 * total + n) // (2 * n)


def main(input_file=None, output_dir=None, analysis_frames=ANALYSIS_FRAMES):
    folder = Path(__file__).resolve().parent

    source = (
        Path(input_file)
        if input_file is not None
        else folder / "defect_results.dat"
    )

    target = (
        Path(output_dir)
        if output_dir is not None
        else source.parent
    )

    # 读取数据。
    with source.open(encoding="utf-8-sig") as f:
        names = f.readline().split()
        data = np.loadtxt(f, ndmin=2)

    required = ("timestep", *COLS)

    # 检查表头。
    if (
        len(names) != len(set(names))
        or any(c not in names for c in required)
    ):
        raise ValueError("缺少必要列或表头重复。")

    # 检查数据行与列数。
    if len(data) < 2 or data.shape[1] != len(names):
        raise ValueError(
            "至少需要两帧数据，且每行列数必须正确。"
        )

    # 只提取需要的列。
    values = data[:, [names.index(c) for c in required]]

    if not np.isfinite(values).all():
        raise ValueError("数据包含 NaN 或无穷值。")

    # 按 timestep 排序。
    values = values[np.argsort(values[:, 0])]

    # ============================================================
    # 只保留前指定帧数。
    # ============================================================
    available_frames = len(values)

    if analysis_frames is None:
        analysis_frames = available_frames
    else:
        if isinstance(analysis_frames, bool) or not isinstance(
            analysis_frames, (int, np.integer)
        ):
            raise ValueError("analysis_frames 必须为正整数或 None。")

        if analysis_frames < 2:
            raise ValueError("analysis_frames 至少需要为 2。")

        if analysis_frames > available_frames:
            raise ValueError(
                f"要求分析前 {analysis_frames} 帧，但 defect_results.dat "
                f"只有 {available_frames} 帧。"
            )

    values = values[:analysis_frames]

    steps = values[:, 0]
    counts = values[:, 1:]
    intervals = np.diff(steps)

    # timestep 必须为整数且不能重复。
    if (
        np.any(steps != np.rint(steps))
        or np.any(intervals <= 0)
    ):
        raise ValueError("时间步必须为整数且不能重复。")

    # 检查采样间隔。
    if not np.all(intervals == intervals[0]):
        raise ValueError(
            "所选分析区间内采样间隔不一致，请先检查缺帧或输出间隔。"
        )

    # 缺陷数量必须是非负整数。
    if (
        np.any(counts < 0)
        or np.any(counts != np.rint(counts))
    ):
        raise ValueError("缺陷数必须为非负整数。")

    # ============================================================
    # 在指定的前 analysis_frames 帧中：
    # 固定丢弃前 25%，只保留后 75%。
    #
    # int() 对正数等价于 floor。
    # 例如：
    #   1000 帧 -> 丢弃 250 帧，统计 750 帧
    #   1001 帧 -> 丢弃 250 帧，统计 751 帧
    # ============================================================
    total_frames = len(counts)
    start = int(total_frames * DISCARD_FRACTION)
    selected = counts[start:]

    if len(selected) < 2:
        raise ValueError(
            "丢弃前 25% 帧后剩余数据不足两帧，无法计算样本 SD。"
        )

    status = (
        f"仅分析前{total_frames}帧；"
        f"固定丢弃其中前25%帧，仅统计后75%帧"
    )

    # 使用保留的全部原始帧计算未取整均值和 SD。
    means = selected.mean(axis=0)
    sds = selected.std(axis=0, ddof=1)

    # 保存统计结果。
    rows = [
        {
            "defect": label,
            "mean": rounded_count_mean(selected[:, i]),
            "raw_mean": float(means[i]),
            "SD": float(sds[i]),
            "n_frames": len(selected),
            "start_step": int(steps[start]),
            "end_step": int(steps[-1]),
            "status": status,
        }
        for i, label in enumerate(LABELS)
    ]

    # 构造 txt 输出内容。
    lines = [
        f"# input: {source.resolve()}",
        f"# status: {status}",
        (
            f"# defect_results.dat 总帧数: {available_frames}；"
            f"本次指定分析前: {total_frames} 帧"
        ),
        (
            f"# 指定分析区间时间步: "
            f"{int(steps[0])} — {int(steps[-1])}"
        ),
        (
            f"# 实际统计时间步: "
            f"{int(steps[start])} — {int(steps[-1])}"
        ),
        (
            f"# 指定分析帧数: {total_frames}；"
            f"舍弃前25%: {start}；统计后75%: {len(selected)}"
        ),
        "# mean为分别四舍五入后的整数；raw_mean保留原始均值",
        "# SD使用原始帧和未取整均值计算，ddof=1；不是SEM",
        "# 独立取整后的总数可能不等于取整后的正、负缺陷数之和",
        "",
    ]

    lines += [
        f"{r['defect']} {r['mean']} ± {r['SD']:.6f}"
        for r in rows
    ]

    lines += [
        "",
        "# 未取整均值（供比较与核查）",
    ]

    lines += [
        f"{r['defect']} raw_mean={r['raw_mean']:.6f}"
        for r in rows
    ]

    text = "\n".join(lines) + "\n"

    # 创建输出目录。
    target.mkdir(parents=True, exist_ok=True)

    # 只输出 txt 文件，不再生成 csv。
    output_file = target / "average_defects.txt"
    output_file.write_text(
        text,
        encoding="utf-8"
    )

    # 同时在终端打印。
    print(text)

    return rows


if __name__ == "__main__":
    main()
