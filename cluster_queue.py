"""Small Windows SSH queue for independent jobs on the twelve audited nodes."""
import argparse
import getpass
import json
import msvcrt
import os
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "cluster_queue.sqlite3"
NODES = json.loads((HERE / "cluster_nodes.json").read_text(encoding="utf-8"))
WORKER = HERE / "cluster_worker.py"
IDENTITY = Path.home() / ".ssh" / "id_ed25519_codex_cluster"


def database():
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, source TEXT NOT NULL, command TEXT NOT NULL,
        kind TEXT NOT NULL, cores INTEGER NOT NULL, memory_gib INTEGER NOT NULL,
        node TEXT, state TEXT NOT NULL, remote TEXT, detail TEXT,
        created REAL NOT NULL, updated REAL NOT NULL)""")
    con.commit()
    return con


def change(con, job_id, **fields):
    fields["updated"] = time.time()
    con.execute("UPDATE jobs SET " + ", ".join(k + "=?" for k in fields) + " WHERE id=?", list(fields.values()) + [job_id])
    con.commit()


def run_process(args, env=None, timeout=90):
    return subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, env=env)


def ssh(node, command, env):
    options = ["-i", str(IDENTITY), "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes"] if IDENTITY.exists() else ["-o", "BatchMode=no", "-o", "NumberOfPasswordPrompts=1"]
    return run_process(["ssh"] + options + ["-o", "StrictHostKeyChecking=accept-new",
                        "-o", "ConnectTimeout=8", "-p", str(node["port"]),
                        "user@" + node["host"], command], env)


def scp(node, source, destination, env, recursive=False):
    options = ["-i", str(IDENTITY), "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes"] if IDENTITY.exists() else ["-o", "BatchMode=no", "-o", "NumberOfPasswordPrompts=1"]
    args = ["scp", "-q"] + options + ["-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=8", "-P", str(node["port"])]
    if recursive:
        args.append("-r")
    return run_process(args + [source, destination], env, timeout=3600)


def upload_tree(node, source, remote, env):
    with tempfile.TemporaryDirectory(prefix="cluster-upload-") as temporary:
        archive = Path(temporary) / "input.tar"
        with tarfile.open(str(archive), "w") as tar:
            for item in source.iterdir():
                tar.add(str(item), arcname=item.name)
        uploaded = scp(node, str(archive), "user@" + node["host"] + ":" + remote + "/.cluster-input.tar", env)
        if uploaded.returncode:
            return uploaded
        return ssh(node, "tar -xf " + shlex.quote(remote + "/.cluster-input.tar") +
                   " -C " + shlex.quote(remote) + " && rm " + shlex.quote(remote + "/.cluster-input.tar"), env)


def credential_env(password):
    # SSH_ASKPASS reads a temporary process variable. The password is not saved to disk.
    fd, name = tempfile.mkstemp(suffix=".cmd", prefix="codex-ssh-askpass-")
    os.close(fd)
    Path(name).write_text("@echo off\necho %CODEX_CLUSTER_PASSWORD%\n", encoding="ascii")
    env = os.environ.copy()
    env.update(SSH_ASKPASS=name, SSH_ASKPASS_REQUIRE="force", DISPLAY="cluster",
               CODEX_CLUSTER_PASSWORD=password)
    return env, name


def probe(node, env):
    command = ("export LC_ALL=C; hostname; nproc; free -m | awk '/^Mem:/ {print $7}'; "
               "df -Pk /home/user | tail -1 | awk '{print $4}'; "
               "uptime | sed 's/.*load average: //'; "
               "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits 2>/dev/null || true")
    result = ssh(node, command, env)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "SSH failed")
    lines = result.stdout.strip().splitlines()
    if len(lines) < 5:
        raise RuntimeError("Incomplete resource report")
    free_mem = int(lines[2]) / 1024
    free_disk = int(lines[3]) / (1024 * 1024)
    load = float(lines[4].split(",")[0].strip())
    gpu_busy = False
    if node["kind"] == "gpu":
        if len(lines) < 6:
            raise RuntimeError("GPU status unavailable")
        usage, memory = [int(part.strip()) for part in lines[5].split(",")[:2]]
        gpu_busy = usage >= 15 or memory >= 1024
    return {"name": lines[0], "free_mem": free_mem, "free_disk": free_disk,
            "load": load, "gpu_busy": gpu_busy}


def refresh(con, env):
    for row in con.execute("SELECT * FROM jobs WHERE state IN ('running','copy_error')").fetchall():
        node = next(n for n in NODES if n["name"] == row["node"])
        marker = row["remote"] + "/.cluster-status.json"
        result = ssh(node, "cat " + shlex.quote(marker), env)
        if result.returncode:
            continue  # A temporary connection failure must not lose the job.
        try:
            status = json.loads(result.stdout)
        except ValueError:
            continue
        if status.get("state") in ("done", "failed"):
            output = HERE / "cluster_results" / row["id"]
            output.parent.mkdir(exist_ok=True)
            size = ssh(node, "du -sk " + shlex.quote(row["remote"]) + " | cut -f1", env)
            if size.returncode:
                change(con, row["id"], state="copy_error", detail=size.stderr[-500:])
                continue
            try:
                required = int(size.stdout.strip()) * 1024
            except ValueError:
                change(con, row["id"], state="copy_error", detail="Could not measure result size")
                continue
            if shutil.disk_usage(str(output.parent)).free < required + 5 * 1024 ** 3:
                change(con, row["id"], state="copy_error", detail="Insufficient local disk space")
                continue
            target = output if not output.exists() else output.parent / (row["id"] + ".retry")
            if target.exists():
                target.rename(output.parent / (row["id"] + ".partial-retry-" + str(int(time.time()))))
            copied = scp(node, "user@" + node["host"] + ":" + row["remote"], str(target), env, True)
            if copied.returncode:
                change(con, row["id"], state="copy_error", detail=copied.stderr[-500:])
            else:
                if target != output:
                    output.rename(output.parent / (row["id"] + ".partial-" + str(int(time.time()))))
                    target.rename(output)
                change(con, row["id"], state=status["state"], detail="exit=" + str(status.get("exit_code")))
                print(row["id"], status["state"], "results:", output)


def dispatch(con, env):
    active = {r["node"] for r in con.execute("SELECT node FROM jobs WHERE state='running'")}
    pending = con.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created").fetchall()
    if not pending:
        return
    candidates = []
    for node in NODES:
        if node["name"] in active:
            continue
        try:
            health = probe(node, env)
            candidates.append((node, health))
        except Exception as exc:
            print(node["name"], "unavailable:", exc)
    for row in pending:
        choices = [(n, h) for n, h in candidates if n["kind"] == row["kind"]
                   and n["cores"] >= row["cores"]
                   and h["free_mem"] >= row["memory_gib"] + 4
                   and h["free_disk"] >= 20
                   and h["load"] < n["cores"] * 0.6
                   and not h["gpu_busy"]]
        if not choices:
            continue
        node, health = max(choices, key=lambda item: item[1]["free_mem"])
        remote = "/home/user/cluster_jobs/" + row["id"]
        source = Path(row["source"])
        source_size = sum(f.stat().st_size for f in source.rglob("*") if f.is_file()) / (1024 ** 3)
        if source_size + 20 > health["free_disk"]:
            continue
        created = ssh(node, "mkdir -p " + shlex.quote(remote), env)
        if created.returncode:
            change(con, row["id"], state="stage_error", detail=created.stderr[-500:])
            continue
        uploaded = upload_tree(node, source, remote, env)
        if uploaded.returncode:
            change(con, row["id"], state="stage_error", detail=uploaded.stderr[-500:])
            continue
        spec = {"command": row["command"]}
        with tempfile.TemporaryDirectory(prefix="cluster-job-") as temporary:
            specfile = Path(temporary) / ".cluster-job.json"
            specfile.write_text(json.dumps(spec), encoding="utf-8")
            for local, filename in [(specfile, ".cluster-job.json"), (WORKER, ".cluster-worker.py")]:
                copied = scp(node, str(local), "user@" + node["host"] + ":" + remote + "/" + filename, env)
                if copied.returncode:
                    change(con, row["id"], state="stage_error", detail=copied.stderr[-500:])
                    break
            else:
                launch = "cd " + shlex.quote(remote) + " && nohup python3 .cluster-worker.py " + shlex.quote(remote) + " </dev/null >/dev/null 2>&1 &"
                started = ssh(node, launch, env)
                if started.returncode:
                    change(con, row["id"], state="stage_error", detail=started.stderr[-500:])
                    continue
                change(con, row["id"], state="running", node=node["name"], remote=remote)
                print(row["id"], "started on", node["name"])
                candidates.remove((node, health))


def main():
    parser = argparse.ArgumentParser(description="Queue independent jobs on the 12 SSH nodes")
    sub = parser.add_subparsers(dest="action", required=True)
    add = sub.add_parser("submit")
    add.add_argument("source", help="Input-only folder to upload")
    add.add_argument("command", help="Linux shell command to run inside that folder")
    add.add_argument("--kind", choices=["cpu", "gpu"], required=True)
    add.add_argument("--cores", type=int, default=4)
    add.add_argument("--memory-gib", type=int, default=8)
    sub.add_parser("status")
    sub.add_parser("nodes")
    sub.add_parser("once", help="Check completed jobs and dispatch waiting jobs")
    sub.add_parser("run", help="Keep checking the queue every minute")
    args = parser.parse_args()
    con = database()
    if args.action == "submit":
        source = Path(args.source).resolve()
        if not source.is_dir() or args.cores < 1 or args.memory_gib < 1:
            parser.error("Source must be a directory; resources must be positive")
        if any(part.name.startswith(".cluster-") for part in source.iterdir()):
            parser.error("Source contains reserved .cluster-* files")
        job_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
        con.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (job_id, str(source), args.command, args.kind, args.cores,
                     args.memory_gib, None, "queued", None, None, time.time(), time.time()))
        con.commit()
        print("Queued", job_id)
        return
    if args.action == "status":
        for row in con.execute("SELECT id,kind,cores,state,node,detail FROM jobs ORDER BY created"):
            print("  ".join(str(value or "-") for value in row))
        return
    if IDENTITY.exists():
        env, askpass = os.environ.copy(), None
    else:
        password = getpass.getpass("SSH password (not saved): ")
        env, askpass = credential_env(password)
    try:
        if args.action == "nodes":
            for node in NODES:
                try:
                    print(node["name"], probe(node, env))
                except Exception as exc:
                    print(node["name"], "unavailable:", exc)
        elif args.action == "once":
            refresh(con, env)
            dispatch(con, env)
        elif args.action == "run":
            with (HERE / "cluster_queue.lock").open("a+b") as lock:
                lock.seek(0)
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    print("Another scheduler is already running")
                    return
                while True:
                    try:
                        refresh(con, env)
                        dispatch(con, env)
                    except Exception as exc:
                        print("Scheduler cycle failed:", repr(exc), flush=True)
                    time.sleep(60)
    finally:
        if askpass and Path(askpass).exists():
            Path(askpass).unlink()


if __name__ == "__main__":
    main()
