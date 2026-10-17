#!/bin/bash

# ============================================================
# Batch post-processing for all F_* folders under the directory
# where THIS run.sh is located.
#
# Usage:
#   cd /home/user/wxd/9.19.2026/nchain30
#   bash run.sh
#
# It also works if called from another directory:
#   bash /home/user/wxd/9.19.2026/nchain30/run.sh
# ============================================================

set -u
set -o pipefail

# Always use the directory containing this run.sh as ROOT.
# Do NOT hard-code nchain10 / nchain30 / etc.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$SCRIPT_DIR"

# Use Python from the currently activated environment.
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Basic checks before starting.
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "错误：找不到 Python：$PYTHON_BIN"
    echo "请先激活正确的 conda 环境，或设置 PYTHON_BIN。"
    exit 1
fi

echo "======================================================================"
echo "run.sh 所在目录 : $SCRIPT_DIR"
echo "实际处理根目录   : $ROOT"
echo "Python           : $(command -v "$PYTHON_BIN")"
echo "======================================================================"
echo

"$PYTHON_BIN" - "$ROOT" <<'PYCODE'
import sys
import re
import subprocess
from pathlib import Path

if sys.version_info < (3, 8):
    print("错误：sphere_nematic_parallel.py 需要 Python 3.8 或以上。")
    print(f"当前解释器：{sys.executable}；版本：{sys.version.split()[0]}")
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    print("错误：当前 Python 环境没有安装 tqdm。")
    print("请执行：pip install tqdm")
    sys.exit(1)


root = Path(sys.argv[1]).resolve()


# ============================================================
# 1. Locate the two processing scripts in ROOT
# ============================================================

def locate_script(root: Path, exact_name: str, fallback_pattern: str) -> Path:
    exact = root / exact_name
    if exact.is_file():
        return exact.resolve()

    candidates = sorted(
        p.resolve()
        for p in root.glob(fallback_pattern)
        if p.is_file()
    )

    if not candidates:
        print(f"错误：在根目录中找不到 {exact_name}")
        print(f"检查目录：{root}")
        sys.exit(1)

    if len(candidates) > 1:
        print(f"错误：找不到正式文件 {exact_name}，但发现多个候选文件：")
        for p in candidates:
            print(f"  {p.name}")
        print("请保留一个明确版本，或将正确版本重命名为：", exact_name)
        sys.exit(1)

    print(f"提示：未找到 {exact_name}，改用 {candidates[0].name}")
    return candidates[0]


convert_src = locate_script(
    root,
    "convert_lammps_to_bd.py",
    "convert_lammps_to_bd*.py",
)

sphere_src = locate_script(
    root,
    "sphere_nematic_parallel.py",
    "sphere_nematic_parallel*.py",
)

# Check the actual analysis script with the same interpreter used by workers.
# --help imports its dependencies but does not read or modify trajectory files.
print("正在检查缺陷分析程序及 NumPy / SciPy 环境 ...", flush=True)
try:
    preflight = subprocess.run(
        [sys.executable, str(sphere_src), "--help"],
        cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", timeout=60,
        check=False,
    )
except (OSError, subprocess.TimeoutExpired) as exc:
    print(f"环境检查无法完成：{exc}")
    sys.exit(1)

if preflight.returncode != 0:
    print(preflight.stdout)
    print(preflight.stderr)
    print(f"环境检查失败：{sys.executable}")
    print("尚未转换任何轨迹。请确认已替换兼容版 sphere_nematic_parallel.py，")
    print("并确认该 Python 环境可导入 numpy、scipy。")
    sys.exit(1)

if "--xyz-output" not in preflight.stdout:
    print("错误：分析脚本版本不匹配，缺少 --xyz-output 参数。")
    sys.exit(1)
print("环境检查通过。", flush=True)


# ============================================================
# 2. Natural sorting for F_* directories
#    Example:
#    F_0.1, F_0.17, F_1, F_5, F_10, F_18 ...
# ============================================================

def natural_key(path: Path):
    m = re.fullmatch(r"F_([-+]?\d+(?:\.\d+)?)", path.name)
    if m:
        try:
            return (0, float(m.group(1)))
        except ValueError:
            pass
    return (1, path.name)


folders = sorted(
    [
        p for p in root.iterdir()
        if p.is_dir()
        and p.name.startswith("F_")
        and p.name != "F_0"
    ],
    key=natural_key,
)

if not folders:
    print(f"错误：{root} 下没有找到需要处理的 F_* 文件夹。")
    sys.exit(1)


print("=" * 70)
print("批量后处理")
print("=" * 70)
print(f"根目录       : {root}")
print(f"转换程序     : {convert_src}")
print(f"缺陷分析程序 : {sphere_src}")
print(f"文件夹数量   : {len(folders)}")
print("排除目录     : F_0")
print()
print("将处理：")
for p in folders:
    print(f"  {p.name}")
print("=" * 70)
print()


success = []
failed = []


# ============================================================
# 3. Determine XYZ format safely
#
# Raw LAMMPS dump:
#   first line == ITEM: TIMESTEP
#
# Converted XYZ:
#   first line == integer particle count
#
# Mixed raw/converted files in the same folder are treated as
# an error, because convert_lammps_to_bd.py overwrites in place.
# ============================================================

def inspect_xyz_format(files):
    raw = []
    converted = []
    invalid = []

    for path in files:
        try:
            with path.open("r", encoding="utf-8") as f:
                first = f.readline().strip()
        except Exception as exc:
            invalid.append((path, f"读取失败：{exc}"))
            continue

        if first == "ITEM: TIMESTEP":
            raw.append(path)
            continue

        try:
            n = int(first)
            if n > 0:
                converted.append(path)
            else:
                invalid.append((path, f"第一行粒子数无效：{first!r}"))
        except ValueError:
            invalid.append((path, f"无法识别第一行：{first!r}"))

    return raw, converted, invalid


# ============================================================
# 4. Process each F_* folder
# ============================================================

pbar = tqdm(
    folders,
    desc="文件夹总进度",
    unit="文件夹",
    dynamic_ncols=True,
)

for folder in pbar:
    pbar.set_postfix_str(folder.name)

    tqdm.write("")
    tqdm.write("=" * 70)
    tqdm.write(f">>> 正在处理：{folder.name}")
    tqdm.write(f">>> 完整路径：{folder}")
    tqdm.write("=" * 70)

    xyz_files = sorted(folder.glob("out-*.xyz"))

    if not xyz_files:
        tqdm.write(f"[{folder.name}] ✗ 没有找到 out-*.xyz，跳过")
        failed.append((folder.name, "没有 out-*.xyz"))
        continue

    tqdm.write(f"[{folder.name}] 找到 {len(xyz_files)} 个 out-*.xyz")

    raw, converted, invalid = inspect_xyz_format(xyz_files)

    if invalid:
        tqdm.write(f"[{folder.name}] ✗ 存在无法识别的 XYZ 文件：")
        for path, reason in invalid[:10]:
            tqdm.write(f"    {path.name}: {reason}")
        if len(invalid) > 10:
            tqdm.write(f"    ... 另外还有 {len(invalid) - 10} 个")
        failed.append((folder.name, "XYZ 格式检查失败"))
        continue

    if raw and converted:
        tqdm.write(
            f"[{folder.name}] ✗ 同一文件夹同时存在原始和已转换 XYZ："
            f"raw={len(raw)}, converted={len(converted)}"
        )
        tqdm.write(
            "为避免对已转换文件再次原地转换，本文件夹不自动继续。"
        )
        failed.append((folder.name, "原始/已转换 XYZ 混合"))
        continue

    # --------------------------------------------------------
    # Step 1/2: convert_lammps_to_bd.py
    #
    # Important:
    # We execute the single source script stored in ROOT while
    # setting cwd=folder. No script is copied into F_* anymore.
    # Therefore stale copies cannot accidentally be executed.
    # --------------------------------------------------------

    if converted and not raw:
        tqdm.write(
            f"[{folder.name}] ⏭ {len(converted)} 个 out-*.xyz "
            "已经是转换格式，跳过 convert_lammps_to_bd.py"
        )
    else:
        tqdm.write("")
        tqdm.write(
            f"[{folder.name}] [1/2] 开始运行 convert_lammps_to_bd.py ..."
        )

        try:
            result = subprocess.run(
                [sys.executable, str(convert_src)],
                cwd=str(folder),
                check=False,
            )
        except Exception as exc:
            tqdm.write(
                f"[{folder.name}] ✗ 无法启动 convert_lammps_to_bd.py：{exc}"
            )
            failed.append((folder.name, "convert_lammps_to_bd.py 启动失败"))
            continue

        if result.returncode != 0:
            tqdm.write(
                f"[{folder.name}] ✗ convert_lammps_to_bd.py "
                f"失败，返回码={result.returncode}"
            )
            failed.append((folder.name, "convert_lammps_to_bd.py 失败"))
            continue

        # Recheck after conversion.
        xyz_files = sorted(folder.glob("out-*.xyz"))
        raw2, converted2, invalid2 = inspect_xyz_format(xyz_files)

        if raw2 or invalid2 or len(converted2) != len(xyz_files):
            tqdm.write(
                f"[{folder.name}] ✗ 转换程序返回成功，但转换后格式检查未通过"
            )
            failed.append((folder.name, "转换后 XYZ 格式检查失败"))
            continue

        tqdm.write(f"[{folder.name}] ✓ XYZ 转换完成")

    # --------------------------------------------------------
    # Step 2/2: sphere_nematic_parallel.py
    #
    # Explicit absolute input/output paths are passed here.
    # This makes it impossible for results to silently go into
    # nchain10 just because the shell was started elsewhere.
    # --------------------------------------------------------

    tqdm.write("")
    tqdm.write(
        f"[{folder.name}] [2/2] 开始运行 sphere_nematic_parallel.py ..."
    )
    tqdm.write(f"[{folder.name}] 输入目录：{folder}")
    tqdm.write(f"[{folder.name}] DAT 输出：{folder / 'results'}")
    tqdm.write(f"[{folder.name}] XYZ 输出：{folder / 'defect_out'}")

    cmd = [
        sys.executable,
        str(sphere_src),
        "--input-dir", str(folder),
        "--pattern", "out-*.xyz",
        "--output", str(folder / "results"),
        "--xyz-output", "defect_out",
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(folder),
            check=False,
        )
    except Exception as exc:
        tqdm.write(
            f"[{folder.name}] ✗ 无法启动 sphere_nematic_parallel.py：{exc}"
        )
        failed.append((folder.name, "sphere_nematic_parallel.py 启动失败"))
        continue

    if result.returncode != 0:
        tqdm.write(
            f"[{folder.name}] ✗ sphere_nematic_parallel.py "
            f"失败，返回码={result.returncode}"
        )
        failed.append((folder.name, "sphere_nematic_parallel.py 失败"))
        continue

    expected_results = [
        folder / "results" / "defect_results.dat",
        folder / "results" / "delaunay.dat",
    ]

    missing_results = [p for p in expected_results if not p.is_file()]
    if missing_results:
        tqdm.write(
            f"[{folder.name}] ✗ Python 返回成功，但预期结果文件不存在："
        )
        for p in missing_results:
            tqdm.write(f"    {p}")
        failed.append((folder.name, "结果文件缺失"))
        continue

    tqdm.write(f"[{folder.name}] ✓ 全部处理完成")
    success.append(folder.name)


# ============================================================
# 5. Final summary
# ============================================================

print()
print("=" * 70)
print("全部任务结束")
print("=" * 70)
print(f"实际处理根目录：{root}")
print(f"成功：{len(success)}/{len(folders)}")

for name in success:
    print(f"  ✓ {name}")

if failed:
    print()
    print(f"失败/跳过：{len(failed)}")
    for name, reason in failed:
        print(f"  ✗ {name}: {reason}")
    print("=" * 70)
    sys.exit(1)

print()
print("✓ 所有文件夹均处理成功")
print("=" * 70)

PYCODE
