#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取 defect_results.dat，固定丢弃前 25% 帧，仅使用后 75% 帧进行统计，
输出整数平均缺陷数 ± 原始样本 SD。

使用：
    与 defect_results.dat 放在同一目录，直接运行。
    不需要填写模拟总时间或稳态起始步数。

方法：
    按帧数固定丢弃前 25% 数据，只保留后 75% 数据进行统计。
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

# 固定舍弃前 25% 帧，只统计后 75%。
DISCARD_FRACTION = 0.25


def rounded_count_mean(values):
    """非负整数计数的均值四舍五入；用整数运算避免 .5 舍入歧义。"""
    n = len(values)
    total = sum(int(value) for value in values)
    return (2 * total + n) // (2 * n)


def main(input_file=None, output_dir=None):
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
            "采样间隔不一致，请先检查缺帧或输出间隔。"
        )

    # 缺陷数量必须是非负整数。
    if (
        np.any(counts < 0)
        or np.any(counts != np.rint(counts))
    ):
        raise ValueError("缺陷数必须为非负整数。")

    # ============================================================
    # 固定丢弃前 25% 帧，只保留后 75% 帧。
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

    status = "固定丢弃前25%帧，仅统计后75%帧"

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
            f"# 固定统计时间步: "
            f"{int(steps[start])} — {int(steps[-1])}"
        ),
        (
            f"# 总帧数: {total_frames}；"
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