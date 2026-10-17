#!/bin/bash

# ============================================================
# run_average.sh
#
# 通用 average defect 批处理程序
#
# 支持两种目录结构：
#
# ------------------------------------------------------------
# 模式 A：独立 run
#
# F_10/
# ├── 1/
# │   └── results/
# │       └── defect_results.dat
# ├── 2/
# │   └── results/
# ├── 3/
# ├── 4/
# ├── 5/
# ├── 6/
# ├── average_defects.py
# └── run_average.sh
#
# ------------------------------------------------------------
# 模式 B：旧的 F_* 结构
#
# nchain30/
# ├── F_0.1/
# │   └── results/
# │       └── defect_results.dat
# ├── F_0.17/
# ├── F_1/
# ├── F_4/
# ├── average_defects.py
# └── run_average.sh
#
# ------------------------------------------------------------
#
# 功能：
#
# 1. 自动使用 run_average.sh 所在目录作为 BASE_DIR
# 2. 优先识别纯数字目录：
#       1/
#       2/
#       3/
#       ...
# 3. 如果没有数字目录，则自动识别：
#       F_0.1/
#       F_1/
#       F_10/
#       ...
# 4. 按数值大小排序
# 5. 检查每个目标目录下的 results/
# 6. 检查 results/defect_results.dat
# 7. 将 average_defects.py 复制进 results/
# 8. 删除旧 average_defects.txt / csv
# 9. 执行 average_defects.py
# 10. 检查新的输出结果
# 11. 显示实时进度
# 12. 最后汇总成功 / 跳过 / 失败
#
# ============================================================


# ============================================================
# 1. Shell 设置
# ============================================================

set -u


# ============================================================
# 2. 自动获得 run_average.sh 所在目录
#
# 对你现在就是：
#
# /home/user/wxd/9.19.2026/nchain10/F_10
#
# ============================================================

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"


# ============================================================
# 3. average_defects.py
# ============================================================

SCRIPT_NAME="average_defects.py"

SOURCE_SCRIPT="${BASE_DIR}/${SCRIPT_NAME}"


# ============================================================
# 4. Python
#
# 默认：
#
# python3
#
# 如果想指定：
#
# PYTHON_BIN=/home/user/anaconda3/bin/python3 ./run_average.sh
#
# ============================================================

PYTHON_BIN="${PYTHON_BIN:-python3}"


# ============================================================
# 5. 检查 Python
# ============================================================

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then

    echo
    echo "============================================================"
    echo "ERROR: 找不到 Python"
    echo "============================================================"
    echo
    echo "Python：$PYTHON_BIN"
    echo

    exit 1

fi


# ============================================================
# 6. 检查 average_defects.py
# ============================================================

if [ ! -f "$SOURCE_SCRIPT" ]; then

    echo
    echo "============================================================"
    echo "ERROR: 找不到 average_defects.py"
    echo "============================================================"
    echo
    echo "应该位于："
    echo
    echo "    $SOURCE_SCRIPT"
    echo
    echo "请确认 average_defects.py 和 run_average.sh"
    echo "位于同一个目录。"
    echo

    exit 1

fi


# ============================================================
# 7. 使用 Python 自动识别目录并批处理
# ============================================================

"$PYTHON_BIN" - "$BASE_DIR" "$SOURCE_SCRIPT" <<'PYCODE'

import sys
import re
import shutil
import subprocess
from pathlib import Path


# ============================================================
# 基本路径
# ============================================================

base_dir = Path(sys.argv[1]).resolve()

source_script = Path(sys.argv[2]).resolve()

python_bin = sys.executable


# ============================================================
# 目录名称规则
# ============================================================

# 纯数字：
#
# 1
# 2
# 3
# ...
#
NUMBER_PATTERN = re.compile(
    r"^\d+$"
)


# 旧版 F_*：
#
# F_0.1
# F_1
# F_10
#
F_PATTERN = re.compile(
    r"^F_([-+]?(?:\d+(?:\.\d*)?|\.\d+))$"
)


# ============================================================
# 1. 优先寻找纯数字目录
# ============================================================

numbered_dirs = []


for path in base_dir.iterdir():

    if not path.is_dir():
        continue

    if NUMBER_PATTERN.fullmatch(path.name):

        numbered_dirs.append(
            (
                int(path.name),
                path
            )
        )


numbered_dirs.sort(
    key=lambda x: x[0]
)


# ============================================================
# 如果存在纯数字目录，使用 numbered 模式
# ============================================================

if numbered_dirs:

    mode = "numbered"

    target_dirs = [
        path
        for _, path in numbered_dirs
    ]


# ============================================================
# 否则寻找旧的 F_* 目录
# ============================================================

else:

    f_dirs = []


    for path in base_dir.iterdir():

        if not path.is_dir():
            continue


        match = F_PATTERN.fullmatch(
            path.name
        )


        if match is None:
            continue


        try:

            f_value = float(
                match.group(1)
            )

        except ValueError:

            continue


        f_dirs.append(
            (
                f_value,
                path
            )
        )


    f_dirs.sort(
        key=lambda x: x[0]
    )


    target_dirs = [
        path
        for _, path in f_dirs
    ]


    mode = "F"


# ============================================================
# 没找到任务
# ============================================================

if not target_dirs:

    print()

    print(
        "=" * 70
    )

    print(
        "ERROR: 没有找到可处理的文件夹"
    )

    print(
        "=" * 70
    )

    print()

    print(
        "支持下面两种结构："
    )

    print()

    print(
        "    1/"
    )

    print(
        "    2/"
    )

    print(
        "    3/"
    )

    print()

    print(
        "或者："
    )

    print()

    print(
        "    F_0.1/"
    )

    print(
        "    F_1/"
    )

    print(
        "    F_10/"
    )

    print()

    print(
        f"当前目录：{base_dir}"
    )

    sys.exit(1)


# ============================================================
# 2. 显示任务
# ============================================================

print()

print(
    "=" * 72
)

print(
    "Average defect number 批量统计"
)

print(
    "=" * 72
)

print()

print(
    f"根目录       : {base_dir}"
)

print(
    f"Python       : {python_bin}"
)

print(
    f"分析脚本     : {source_script.name}"
)


if mode == "numbered":

    print(
        "目录模式     : numbered runs"
    )

    print(
        "               1/, 2/, 3/, ..."
    )

else:

    print(
        "目录模式     : F_*"
    )


print(
    f"任务数量     : {len(target_dirs)}"
)

print()

print(
    "将依次处理："
)

print()


for index, folder in enumerate(
    target_dirs,
    start=1
):

    print(
        f"    [{index:02d}] "
        f"{folder.name}/results/"
    )


print()

print(
    "=" * 72
)

print()


# ============================================================
# 3. 统计变量
# ============================================================

success = []

skipped = []

failed = []


total = len(target_dirs)


# ============================================================
# 4. 开始逐个处理
# ============================================================

for current, folder in enumerate(
    target_dirs,
    start=1
):


    # --------------------------------------------------------
    # 百分比
    # --------------------------------------------------------

    percent = (
        current
        / total
        * 100.0
    )


    # --------------------------------------------------------
    # 路径
    # --------------------------------------------------------

    results_dir = (
        folder
        / "results"
    )


    data_file = (
        results_dir
        / "defect_results.dat"
    )


    target_script = (
        results_dir
        / "average_defects.py"
    )


    output_txt = (
        results_dir
        / "average_defects.txt"
    )


    output_csv = (
        results_dir
        / "average_defects.csv"
    )


    print()

    print(
        "=" * 72
    )

    print(
        f"[{current}/{total}] "
        f"{percent:6.2f}%    "
        f"正在处理：{folder.name}"
    )

    print(
        "=" * 72
    )

    print(
        f"run     : {folder}"
    )

    print(
        f"results : {results_dir}"
    )

    print()


    # ========================================================
    # STEP 1
    # 检查 results/
    # ========================================================

    if not results_dir.is_dir():

        print(
            "WARNING:"
        )

        print()

        print(
            "    找不到 results 文件夹："
        )

        print(
            f"    {results_dir}"
        )

        print()

        print(
            f"    跳过 {folder.name}"
        )

        skipped.append(
            (
                folder.name,
                "缺少 results/"
            )
        )

        continue


    # ========================================================
    # STEP 2
    # 检查 defect_results.dat
    # ========================================================

    if not data_file.is_file():

        print(
            "WARNING:"
        )

        print()

        print(
            "    找不到 defect_results.dat："
        )

        print(
            f"    {data_file}"
        )

        print()

        print(
            f"    跳过 {folder.name}"
        )

        skipped.append(
            (
                folder.name,
                "缺少 defect_results.dat"
            )
        )

        continue


    print(
        "[1/4] ✓ 找到 defect_results.dat"
    )


    # ========================================================
    # STEP 3
    # 复制 average_defects.py
    # ========================================================

    print()

    print(
        "[2/4] 复制 average_defects.py ..."
    )


    try:

        shutil.copy2(
            source_script,
            target_script
        )


    except Exception as exc:

        print()

        print(
            f"      ✗ 复制失败：{exc}"
        )

        failed.append(
            (
                folder.name,
                f"复制 average_defects.py 失败：{exc}"
            )
        )

        continue


    print(
        "      ✓ 复制完成"
    )


    # ========================================================
    # STEP 4
    # 删除旧结果
    #
    # 防止本次运行失败时误认旧文件是新结果。
    # ========================================================

    print()

    print(
        "[3/4] 清理旧结果 ..."
    )


    try:

        if output_txt.exists():

            output_txt.unlink()


        if output_csv.exists():

            output_csv.unlink()


    except Exception as exc:

        print(
            f"      ✗ 删除旧输出失败：{exc}"
        )

        failed.append(
            (
                folder.name,
                f"清理旧输出失败：{exc}"
            )
        )

        continue


    print(
        "      ✓ 旧结果清理完成"
    )


    # ========================================================
    # STEP 5
    # 执行 average_defects.py
    # ========================================================

    print()

    print(
        "[4/4] 执行 average_defects.py ..."
    )

    print()

    print(
        "-" * 72
    )


    try:

        result = subprocess.run(

            [
                python_bin,
                "average_defects.py"
            ],

            cwd=str(
                results_dir
            ),

            check=False
        )


    except Exception as exc:

        print()

        print(
            "-" * 72
        )

        print()

        print(
            f"ERROR: average_defects.py 启动失败：{exc}"
        )

        failed.append(
            (
                folder.name,
                f"Python 启动失败：{exc}"
            )
        )

        continue


    print(
        "-" * 72
    )

    print()


    # ========================================================
    # STEP 6
    # 检查 Python 返回码
    # ========================================================

    if result.returncode != 0:

        print(
            "ERROR:"
        )

        print()

        print(
            f"    {folder.name} 计算失败"
        )

        print(
            f"    Python return code = "
            f"{result.returncode}"
        )

        failed.append(
            (
                folder.name,
                (
                    "average_defects.py 失败，"
                    f"return code = "
                    f"{result.returncode}"
                )
            )
        )

        continue


    # ========================================================
    # STEP 7
    # 检查 TXT 输出
    # ========================================================

    if not output_txt.is_file():

        print(
            "ERROR:"
        )

        print()

        print(
            "    Python 返回成功，"
        )

        print(
            "    但没有生成："
        )

        print()

        print(
            f"    {output_txt}"
        )

        failed.append(
            (
                folder.name,
                "未生成 average_defects.txt"
            )
        )

        continue


    # ========================================================
    # 成功
    # ========================================================

    print(
        f"✓ SUCCESS: {folder.name} 处理完成"
    )

    print()

    print(
        "输出："
    )

    print(
        f"    {output_txt}"
    )


    if output_csv.is_file():

        print(
            f"    {output_csv}"
        )


    success.append(
        folder.name
    )


# ============================================================
# 5. 最终统计
# ============================================================

print()

print()

print(
    "#" * 72
)

print(
    "#                         全部处理结束"
)

print(
    "#" * 72
)

print()

print(
    f"根目录     : {base_dir}"
)

print(
    f"目录模式   : {mode}"
)

print(
    f"总任务数量 : {total}"
)

print(
    f"成功数量   : {len(success)}"
)

print(
    f"跳过数量   : {len(skipped)}"
)

print(
    f"失败数量   : {len(failed)}"
)

print()


# ============================================================
# 成功
# ============================================================

if success:

    print(
        "-" * 72
    )

    print(
        "成功："
    )

    print(
        "-" * 72
    )


    for name in success:

        print(
            f"    ✓ {name}"
        )


    print()


# ============================================================
# 跳过
# ============================================================

if skipped:

    print(
        "-" * 72
    )

    print(
        "跳过："
    )

    print(
        "-" * 72
    )


    for name, reason in skipped:

        print(
            f"    ⏭ {name}: {reason}"
        )


    print()


# ============================================================
# 失败
# ============================================================

if failed:

    print(
        "-" * 72
    )

    print(
        "失败："
    )

    print(
        "-" * 72
    )


    for name, reason in failed:

        print(
            f"    ✗ {name}: {reason}"
        )


    print()


# ============================================================
# 输出位置
# ============================================================

print(
    "-" * 72
)

print(
    "输出文件位置："
)

print(
    "-" * 72
)

print()


if mode == "numbered":

    print(
        "    1/results/average_defects.txt"
    )

    print(
        "    2/results/average_defects.txt"
    )

    print(
        "    ..."
    )

else:

    print(
        "    F_*/results/average_defects.txt"
    )


print()

print(
    "#" * 72
)


# ============================================================
# 返回码
#
# 有真正失败 -> 1
#
# 只有 skipped 不视为程序崩溃。
# ============================================================

if failed:

    sys.exit(1)

else:

    sys.exit(0)


PYCODE