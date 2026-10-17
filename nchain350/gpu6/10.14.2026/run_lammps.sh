#!/bin/bash

# ============================================================
# run_lammps.sh
#
# 功能：
#   自动寻找当前目录下所有 F_* 文件夹
#   并分别在其中运行：
#
#   nohup mpirun -np 4 lmp -in bd.in > nohup.out 2>&1 &
#
# 例如：
#
# nchain100/
# ├── F_0/
# ├── F_0.1/
# ├── F_0.17/
# ├── F_0.55/
# ├── F_1/
# ├── F_5/
# ├── F_10/
# ├── F_15/
# └── run_lammps.sh
#
# ============================================================

set -u
set -o pipefail


# ============================================================
# 1. 自动获取 run_lammps.sh 所在目录
# ============================================================

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"


# ============================================================
# 2. 用户参数
# ============================================================

# 每个工况使用的 MPI 进程数
NP=4

# MPI 命令
MPI_BIN="${MPI_BIN:-mpirun}"

# LAMMPS 命令
LAMMPS_BIN="${LAMMPS_BIN:-lmp}"


# ============================================================
# 3. 检查 mpirun 和 lmp
# ============================================================

if ! command -v "$MPI_BIN" >/dev/null 2>&1; then
    echo
    echo "ERROR: 找不到 mpirun"
    echo
    exit 1
fi


if ! command -v "$LAMMPS_BIN" >/dev/null 2>&1; then
    echo
    echo "ERROR: 找不到 lmp"
    echo
    echo "当前 PATH 中没有可执行的 LAMMPS。"
    echo
    echo "可以检查："
    echo
    echo "    which lmp"
    echo
    echo "    type -a lmp"
    echo
    exit 1
fi


# ============================================================
# 4. 自动寻找 F_* 文件夹
#
# sort -V 会得到类似：
#
# F_0
# F_0.1
# F_0.17
# F_0.55
# F_1
# F_5
# F_10
# F_15
#
# 而不是错误的字符串排序：
#
# F_1
# F_10
# F_15
# F_5
#
# ============================================================

mapfile -t DIRS < <(
    find "$ROOT" \
        -mindepth 1 \
        -maxdepth 1 \
        -type d \
        -name 'F_*' \
        -printf '%f\n' \
        | sort -V
)


TOTAL=${#DIRS[@]}


if [ "$TOTAL" -eq 0 ]; then
    echo
    echo "ERROR: 在以下目录中没有找到 F_* 文件夹："
    echo
    echo "    $ROOT"
    echo
    exit 1
fi


# ============================================================
# 5. PID 记录文件
# ============================================================

PID_FILE="${ROOT}/lammps_jobs.pid"

# 本次运行重新创建
: > "$PID_FILE"


# ============================================================
# 6. 显示任务信息
# ============================================================

echo
echo "======================================================================"
echo "LAMMPS 批量提交"
echo "======================================================================"
echo
echo "ROOT       : $ROOT"
echo "MPI        : $(command -v "$MPI_BIN")"
echo "LAMMPS     : $(command -v "$LAMMPS_BIN")"
echo "MPI ranks  : $NP / job"
echo "任务数量   : $TOTAL"
echo
echo "即将运行："
echo


INDEX=0

for DIR_NAME in "${DIRS[@]}"; do

    INDEX=$((INDEX + 1))

    printf "    [%02d] %s\n" \
        "$INDEX" \
        "$DIR_NAME"

done


echo
echo "理论最大 MPI ranks：$((TOTAL * NP))"
echo
echo "======================================================================"
echo


# ============================================================
# 7. 开始提交
# ============================================================

SUCCESS=0
SKIPPED=0
FAILED=0
CURRENT=0


for DIR_NAME in "${DIRS[@]}"; do

    CURRENT=$((CURRENT + 1))

    DIR="${ROOT}/${DIR_NAME}"

    PERCENT=$((CURRENT * 100 / TOTAL))


    echo
    echo "----------------------------------------------------------------------"
    echo "[$CURRENT/$TOTAL] ${PERCENT}%    $DIR_NAME"
    echo "----------------------------------------------------------------------"


    # ========================================================
    # 检查 bd.in
    # ========================================================

    if [ ! -f "${DIR}/bd.in" ]; then

        echo "WARNING: 找不到"
        echo
        echo "    ${DIR}/bd.in"
        echo
        echo "跳过 $DIR_NAME"

        SKIPPED=$((SKIPPED + 1))

        continue

    fi


    # ========================================================
    # 如果之前存在 PID 文件，检查任务是否还活着
    # ========================================================

    LOCAL_PID_FILE="${DIR}/lammps.pid"


    if [ -f "$LOCAL_PID_FILE" ]; then

        OLD_PID="$(cat "$LOCAL_PID_FILE" 2>/dev/null || true)"


        if [[ "$OLD_PID" =~ ^[0-9]+$ ]] && kill -0 "$OLD_PID" 2>/dev/null; then

            echo "WARNING: $DIR_NAME 似乎已经在运行"
            echo
            echo "    PID = $OLD_PID"
            echo
            echo "为避免重复提交，本次跳过。"

            SKIPPED=$((SKIPPED + 1))

            continue

        else

            # PID 已失效
            rm -f "$LOCAL_PID_FILE"

        fi

    fi


    # ========================================================
    # 进入目录
    # ========================================================

    if ! cd "$DIR"; then

        echo "ERROR: 无法进入目录："
        echo
        echo "    $DIR"

        FAILED=$((FAILED + 1))

        continue

    fi


    # ========================================================
    # 启动 LAMMPS
    # ========================================================

    echo "启动："
    echo
    echo "    nohup $MPI_BIN -np $NP $LAMMPS_BIN -in bd.in > nohup.out 2>&1 &"
    echo


    nohup "$MPI_BIN" \
        -np "$NP" \
        "$LAMMPS_BIN" \
        -in bd.in \
        > nohup.out 2>&1 &


    PID=$!


    # 保存到工况目录
    echo "$PID" > lammps.pid

    # 保存到总 PID 文件
    printf "%-12s %s\n" \
        "$DIR_NAME" \
        "$PID" \
        >> "$PID_FILE"


    # ========================================================
    # 稍微等待一下，检查进程有没有立即崩溃
    # ========================================================

    sleep 1


    if kill -0 "$PID" 2>/dev/null; then

        echo "✓ 启动成功"
        echo
        echo "    工况      : $DIR_NAME"
        echo "    PID       : $PID"
        echo "    MPI ranks : $NP"
        echo "    日志      : ${DIR}/nohup.out"

        SUCCESS=$((SUCCESS + 1))

    else

        echo "✗ 任务启动后立即退出"
        echo
        echo "请检查："
        echo
        echo "    ${DIR}/nohup.out"

        rm -f lammps.pid

        FAILED=$((FAILED + 1))

    fi


done


# ============================================================
# 8. 返回根目录
# ============================================================

cd "$ROOT" || exit 1


# ============================================================
# 9. 汇总
# ============================================================

echo
echo
echo "======================================================================"
echo "全部提交完成"
echo "======================================================================"
echo
echo "总工况数：$TOTAL"
echo "成功启动：$SUCCESS"
echo "跳过数量：$SKIPPED"
echo "失败数量：$FAILED"
echo
echo "总 PID 文件："
echo
echo "    $PID_FILE"
echo


if [ -s "$PID_FILE" ]; then

    echo "本次启动的任务："
    echo

    cat "$PID_FILE"

fi


echo
echo "======================================================================"
echo
echo "查看 LAMMPS 进程："
echo
echo '    ps -u "$USER" -o pid,ppid,stat,%cpu,%mem,etime,cmd | grep -E "mpirun|lmp" | grep -v grep'
echo
echo "实时查看某个工况："
echo
echo "    tail -f F_10/nohup.out"
echo
echo "======================================================================"
echo


# ============================================================
# 10. 返回码
# ============================================================

if [ "$FAILED" -gt 0 ]; then
    exit 1
else
    exit 0
fi