#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import time
import uuid
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

log = logging.getLogger("vote1000")

# 构建标记：每次运行会打印，用于确认 Spyder/编辑器加载的是最新版文件
__BUILD__ = "2026-10-17 http-driver v2"

# ============================================================
# 一、日志脱敏（与 vote_probe 保持一致）
# ============================================================
SENSITIVE_HEADERS = {
    "authorization", "cookie", "x-csrf-token", "x-xsrf-token",
    "x-auth-token", "x-api-key", "set-cookie", "proxy-authorization",
}
SENSITIVE_QUERY_KEYS = {"token", "csrf", "auth", "session", "sig", "signature", "key"}


def mask_secret(value: str, head: int = 4, tail: int = 2) -> str:
    if not value:
        return ""
    if len(value) <= head + tail:
        return "*" * len(value)
    return f"{value[:head]}{'*' * (len(value) - head - tail)}{value[-tail:]}"


def mask_url(url: str) -> str:
    try:
        p = urllib.parse.urlparse(url)
    except Exception:
        return "<无法解析的 URL>"
    if p.query:
        parts = []
        for kv in p.query.split("&"):
            if "=" in kv:
                k, v = kv.split("=", 1)
            else:
                k, v = kv, ""
            if k.lower() in SENSITIVE_QUERY_KEYS:
                v = mask_secret(v)
            parts.append(f"{k}={v}")
        query = "&".join(parts)
    else:
        query = ""
    return urllib.parse.urlunparse((p.scheme, p.netloc, p.path, "", query, ""))


def mask_headers(headers: Dict[str, str]) -> Dict[str, str]:
    out = {}
    for k, v in (headers or {}).items():
        if k.lower() in SENSITIVE_HEADERS:
            if k.lower() == "cookie":
                pairs = []
                for item in (v or "").split(";"):
                    item = item.strip()
                    if "=" in item:
                        kk, vv = item.split("=", 1)
                        pairs.append(f"{kk}={mask_secret(vv)}")
                    elif item:
                        pairs.append(item)
                out[k] = "; ".join(pairs)
            else:
                out[k] = mask_secret(v)
        else:
            out[k] = v
    return out


# ============================================================
# 二、配置与动作模型
# ============================================================
@dataclass
class VoteConfig:
    # 目标
    vote_url: str                 # 投票页（先访问它建立会话/CSRF）
    submit_url: str               # 真正提交投票的接口
    method: str = "POST"
    data: str = ""                # 原始请求体（表单 / JSON 字符串）
    content_type: str = "application/x-www-form-urlencoded"
    success_field: str = "success"
    success_value: str = "true"

    # 数量
    total_votes: int = 1000
    per_profile: int = 10         # 每个 profile 投多少次（= 单浏览器上限）

    # 节奏
    between_vote_delay: float = 1.0     # 同 profile 内两票间隔
    between_profile_delay: float = 2.0   # 换 profile 间隔
    timeout: float = 20.0

    # 指纹随机化
    randomize_fingerprint: bool = True
    ua_list: List[str] = field(default_factory=list)
    viewport_list: List[str] = field(default_factory=list)
    tz_list: List[str] = field(default_factory=list)
    lang_list: List[str] = field(default_factory=list)

    # 驱动
    driver: str = "auto"          # auto / cdp / playwright
    chrome_path: str = ""         # 留空自动探测
    headless: bool = False

    # 输出
    out: Optional[str] = None
    stop_on_fail: bool = False
    keep_profiles: bool = False   # True 保留 profile 目录便于排查

    # 重试
    max_retries_per_vote: int = 2

    # 代理 / IP 轮换
    proxy: str = ""               # 单个代理，如 "http://127.0.0.1:7890"
    proxy_list: List[str] = field(default_factory=list)  # 代理列表，自动轮换

    # 草莓云/FlClash 自动轮换（可选）
    flclash_api: str = ""         # FlClash API 地址，如 http://127.0.0.1:9090
    flclash_proxy_group: str = "GLOBAL"  # FlClash 代理组名
    flclash_switch_on_profile: bool = False  # 每个 profile 切换一次节点

    # HTTP 模式（无浏览器）
    http_warmup: bool = False     # 是否先 GET 投票页预热（建立会话/拿 CSRF Cookie）


@dataclass
class ActionScript:
    """
    动作脚本（JSON），描述"打开页面后如何完成一次投票"。
    支持把浏览器抓包得到的真实提交逻辑固化下来：

    {
      "vote_url": "https://x.com/vote.php?id=19",
      "submit_url": "https://x.com/ajax/vote",
      "method": "POST",
      "content_type": "application/x-www-form-urlencoded",
      "data": "choice={{choice}}&from=probe&ts={{ts}}",   # {{choice}}/{{ts}}/{{uuid}} 占位符
      "success_field": "success",
      "success_value": "true",
      "choice_values": ["1", "2", "3"],     # 每次投票随机取一个
      "pre_click": ["#submit-btn"],          # 可选：提交前先点这些按钮
      "pre_select": {"#choice": "{{choice}}"}  # 可选：先选中某选项再提交
    }
    """
    vote_url: str
    submit_url: str
    method: str = "POST"
    content_type: str = "application/x-www-form-urlencoded"
    data: str = ""
    success_field: str = "success"
    success_value: str = "true"
    choice_values: List[str] = field(default_factory=lambda: ["1"])
    pre_click: List[str] = field(default_factory=list)
    pre_select: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str) -> "ActionScript":
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        known = {k: d.pop(k, None) for k in
                 ("vote_url", "submit_url", "method", "content_type", "data",
                  "success_field", "success_value", "choice_values",
                  "pre_click", "pre_select") if k in d}
        return cls(**known)


def fill_template(s: str, ctx: Dict[str, Any]) -> str:
    """把 {{key}} 替换成 ctx[key]。"""
    out = s
    for k, v in ctx.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


# ============================================================
# 三、Chrome / Edge 探测
# ============================================================
def find_chrome() -> Optional[str]:
    """返回可用的 Chrome/Edge 可执行路径；找不到返回 None。"""
    candidates = [
        r"C:/Program Files/Google/Chrome/Application/chrome.exe",
        r"C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
        r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        r"C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    # 兜底：常见目录递归
    import glob
    for pat in (r"C:/Program Files/Google/Chrome/Application/chrome.exe",
                r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"):
        m = glob.glob(pat)
        if m:
            return m[0]
    return None


# ============================================================
# 四、指纹池
# ============================================================
DEFAULT_UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]
DEFAULT_VIEWPORT = ["1920x1080", "1366x768", "1536x864", "1440x900", "1280x800"]
DEFAULT_TZ = ["Asia/Shanghai", "Asia/Shanghai", "Asia/Shanghai", "Asia/Shanghai",
              "Asia/Tokyo", "Asia/Seoul", "America/New_York", "Europe/London"]
DEFAULT_LANG = ["zh-CN", "zh-CN", "zh-CN", "zh-TW", "en-US"]


def pick_fp(cfg: VoteConfig, kind: str) -> str:
    if kind == "ua":
        pool = cfg.ua_list or DEFAULT_UA
    elif kind == "viewport":
        pool = cfg.viewport_list or DEFAULT_VIEWPORT
    elif kind == "tz":
        pool = cfg.tz_list or DEFAULT_TZ
    elif kind == "lang":
        pool = cfg.lang_list or DEFAULT_LANG
    else:
        return ""
    return random.choice(pool) if cfg.randomize_fingerprint else (pool[0] if pool else "")




# ============================================================
# 五、纯标准库 CDP（Chrome DevTools Protocol）客户端
# ============================================================
import socket
import struct
import base64
import threading

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class CDPError(Exception):
    pass


def _http_get_json(url: str, timeout: float = 10.0):
    req = urllib.request.Request(url, headers={"User-Agent": "vote1000/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def wait_for_devtools(cdp_port: int, chrome_dir: str, timeout: float = 30.0):
    """轮询 CDP /json 列表，直到至少 1 个 page target 出现，返回 ws url。"""
    deadline = time.time() + timeout
    last_err = None
    log.debug("等待 DevTools 端口 %d 就绪（超时 %.1fs）...", cdp_port, timeout)
    while time.time() < deadline:
        try:
            targets = _http_get_json(f"http://127.0.0.1:{cdp_port}/json/list", timeout=5.0)
            for t in targets:
                if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                    log.debug("DevTools 已就绪，找到 page target: %s", t.get("title", ""))
                    return t["webSocketDebuggerUrl"], t.get("id")
        except Exception as e:
            last_err = e
            log.debug("DevTools 尚未就绪: %s", e)
        time.sleep(0.3)
    # 尝试读取 Chrome 日志，帮助诊断（中文 Windows 常用 GBK）
    chrome_log = os.path.join(os.path.dirname(chrome_dir), f"chrome_{os.path.basename(chrome_dir)}.log")
    log_snippet = ""
    if os.path.isfile(chrome_log):
        # Chrome 在中文 Windows 上输出 GBK，优先用 GBK 解码
        try:
            with open(chrome_log, "rb") as f:
                raw = f.read()
            if raw.strip():
                for enc in ("gbk", "gb2312", "gb18030", "utf-8", "latin-1"):
                    try:
                        text = raw.decode(enc, errors="replace")
                        lines = text.splitlines()[-20:]
                        log_snippet = "\n  Chrome 日志最后 20 行:\n  " + "\n  ".join(lines)
                        break
                    except Exception:
                        continue
        except Exception:
            pass
    raise CDPError(f"等待 DevTools 超时：{last_err}{log_snippet}")


# ============================================================
# 三.5、纯标准库 WebSocket 客户端（连接 Chrome DevTools Protocol）
# ============================================================
class WebSocket:
    """纯标准库实现的 WebSocket 客户端（用于连接 Chrome DevTools Protocol）。

    仅支持 RFC6455 的基础握手 + 文本帧收发，足够驱动 CDP。
    不依赖任何第三方库（websocket-client / websockets 等）。
    """

    def __init__(self, ws_url: str, timeout: float = 15.0):
        # ws://host:port/path
        m = re.match(r"ws://([^:/]+):(\d+)(.*)", ws_url)
        if not m:
            raise CDPError(f"不支持的 ws url: {ws_url}")
        host, port, path = m.group(1), int(m.group(2)), m.group(3) or "/"
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.path = path
        self._send_key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {self._send_key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
        # 读握手响应
        resp = self._read_http_response()
        if b"101" not in resp:
            raise CDPError(f"WebSocket 握手失败: {resp[:120]!r}")
        # 握手成功后立即启动事件泵（避免服务端首个帧早于线程启动）
        self._id = 0
        self._events = []
        self._cv = threading.Condition()
        self._closed = False
        self._event_thread = threading.Thread(target=self._pump, daemon=True)
        self._event_thread.start()

    def _read_http_response(self) -> bytes:
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        return buf

    def _pump(self):
        try:
            while not self._closed:
                data = self._recv_frame()
                if data is None:
                    break
                try:
                    msg = json.loads(data.decode("utf-8"))
                except Exception:
                    continue
                with self._cv:
                    self._events.append(msg)
                    self._cv.notify_all()
        except Exception:
            pass

    def _recv_frame(self) -> Optional[bytes]:
        if self._closed:
            return None
        b1 = self._read_exact(1)
        if not b1:
            return None
        b2 = self._read_exact(1)
        mask = b2[0] & 0x80   # MASK 位在第二个字节，不是第一个
        opcode = b1[0] & 0x0F
        length = b2[0] & 0x7F
        if length == 126:
            length = struct.unpack(">H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self._read_exact(8))[0]
        if mask:
            raise CDPError("服务端不应发掩码帧")
        payload = self._read_exact(length) if length else b""
        if opcode == 8:  # close
            self._closed = True
            return None
        return payload

    def _read_exact(self, n: int) -> bytes:
        if n == 0:
            return b""
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise CDPError("连接被关闭")
            buf += chunk
        return buf

    def send_command(self, method: str, params: Optional[Dict] = None) -> Dict:
        self._id += 1
        cmd_id = self._id
        payload = json.dumps({"id": cmd_id, "method": method, "params": params or {}}).encode()
        # 客户端发掩码帧
        mask = os.urandom(4)
        length = len(payload)
        if length < 126:
            header = bytes([0x81, 0x80 | length])
        elif length < 65536:
            header = bytes([0x81, 0x80 | 126]) + struct.pack(">H", length)
        else:
            header = bytes([0x81, 0x80 | 127]) + struct.pack(">Q", length)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(header + mask + masked)
        # 等匹配 id 的响应
        deadline = time.time() + 30
        with self._cv:
            while True:
                while self._events:
                    msg = self._events.pop(0)
                    if msg.get("id") == cmd_id:
                        if "error" in msg:
                            raise CDPError(msg["error"].get("message", str(msg["error"])))
                        return msg.get("result", {})
                if time.time() > deadline:
                    raise CDPError(f"等 {method} 响应超时")
                self._cv.wait(0.5)

    def close(self):
        self._closed = True
        try:
            self.sock.close()
        except Exception:
            pass


# ============================================================
# 三.6、FlClash / 草莓云 自动节点轮换（可选）
# ============================================================
class FlClashController:
    """通过 FlClash/草莓云 external-controller API 自动切换代理节点。
    
    使用前需要在 FlClash 配置中开启 external-controller（通常地址是 127.0.0.1:9090）。
    如果 API 不可用，会自动降级为不切换。
    """

    def __init__(self, api_url: str, proxy_group: str = "GLOBAL"):
        self.api_url = api_url.rstrip("/")
        self.proxy_group = proxy_group
        self._proxies_cache: Optional[Dict] = None
        self._current_node: str = ""
        self._node_list: List[str] = []

    def _api(self, path: str, method: str = "GET", body: Optional[Dict] = None) -> Optional[Dict]:
        try:
            url = f"{self.api_url}{path}"
            data = json.dumps(body).encode("utf-8") if body else None
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            log.debug("FlClash API 请求失败 %s %s: %s", method, path, e)
            return None

    def refresh(self) -> bool:
        """刷新代理组节点列表。"""
        data = self._api("/proxies")
        if not data:
            return False
        group = data.get("proxies", {}).get(self.proxy_group, {})
        self._node_list = group.get("all", [])
        self._current_node = group.get("now", "")
        self._proxies_cache = data
        return bool(self._node_list)

    def switch_next(self) -> Optional[str]:
        """切换到下一个节点（轮询），返回切换后的节点名。"""
        if not self._node_list and not self.refresh():
            return None
        if not self._node_list:
            return None
        try:
            idx = self._node_list.index(self._current_node)
        except ValueError:
            idx = -1
        next_node = self._node_list[(idx + 1) % len(self._node_list)]
        ok = self._api(f"/proxies/{urllib.parse.quote(self.proxy_group)}", method="PUT",
                       body={"name": next_node})
        if ok is not None:
            self._current_node = next_node
            log.info("[FlClash] 已切换节点: %s -> %s", self._current_node, next_node)
            return next_node
        return None

    @property
    def available(self) -> bool:
        return bool(self._node_list or self.refresh())


def _is_port_in_use(port: int) -> bool:
    """检查端口是否被占用（纯标准库实现，无需 psutil）。"""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


def _kill_process_on_port(port: int) -> bool:
    """尝试终止占用指定端口的进程（Windows 专用）。"""
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "TCP"],
            text=True, errors="replace", timeout=10,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        )
        pid = None
        for line in out.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                if parts:
                    pid = parts[-1]
                    break
        if pid:
            subprocess.run(["taskkill", "/F", "/PID", pid],
                           capture_output=True, timeout=5,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            time.sleep(0.5)
            return True
    except Exception:
        pass
    return False


def _kill_all_chrome() -> None:
    """强制终止所有 Chrome 和 Edge 进程，防止 Chrome 复用已有会话。
    
    根因：Chrome 在 Windows 上检测到已有实例时，会把新 profile 的启动
    请求塞进已有窗口（输出'正在现有的浏览器会话中打开'），导致 CDP
    端口永远不监听，wait_for_devtools 超时。
    """
    for name in ("chrome.exe", "msedge.exe", "Google Chrome", "Microsoft Edge"):
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", name],
                capture_output=True, timeout=8,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
        except Exception:
            pass
    time.sleep(0.8)


def launch_chrome(chrome_path: str, user_data_dir: str, cdp_port: int,
                  headless: bool = False, proxy: str = "") -> subprocess.Popen:
    """启动一个隔离的 Chrome/Edge 实例（独立 profile + CDP 端口）。"""
    # 【核心修复】先杀所有 Chrome/Edge 进程，防止 Chrome 复用已有会话
    # （Chrome 检测到已有实例时会输出'正在现有的浏览器会话中打开'，
    #   导致 CDP 端口永远不监听，wait_for_devtools 超时）
    _kill_all_chrome()

    # 清理端口残留
    if _is_port_in_use(cdp_port):
        log.warning("端口 %d 被占用，尝试清理...", cdp_port)
        _kill_process_on_port(cdp_port)
        time.sleep(0.5)
        if _is_port_in_use(cdp_port):
            cdp_port = cdp_port + 100
            log.warning("端口仍被占用，切换到备用端口 %d", cdp_port)

    # 清理锁文件和旧 profile 目录
    if os.path.isdir(user_data_dir):
        for lock_name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            lock = os.path.join(user_data_dir, lock_name)
            if os.path.exists(lock):
                try:
                    os.remove(lock)
                except Exception:
                    pass
        try:
            shutil.rmtree(user_data_dir)
        except Exception:
            pass

    os.makedirs(user_data_dir, exist_ok=True)

    args = [
        chrome_path,
        f"--remote-debugging-port={cdp_port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-component-extensions-with-defaults",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--no-remote",
        "--new-window",          # 强制开新窗口，不复用已有
    ]
    if headless:
        args.append("--headless=new")
    # 【修复】显式传递代理给 Chrome，确保走代理
    if proxy:
        args.append(f"--proxy-server={proxy}")
        log.debug("Chrome 使用代理: %s", proxy)

    log.info("启动浏览器: %s port=%d profile=%s",
             os.path.basename(chrome_path), cdp_port,
             os.path.basename(user_data_dir))

    # Chrome 日志用二进制写入，避免编码问题
    chrome_log = os.path.join(os.path.dirname(user_data_dir),
                              f"chrome_{os.path.basename(user_data_dir)}.log")
    try:
        fout = open(chrome_log, "wb")
    except Exception:
        fout = subprocess.DEVNULL

    proc = subprocess.Popen(args, stdout=fout, stderr=subprocess.STDOUT,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return proc


def _kill_existing_chrome(cdp_port: int) -> None:
    """检查并终止占用指定调试端口的 Chrome 进程（避免复用现有会话）。"""
    try:
        # 查找监听指定端口的进程
        import psutil
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr.port == cdp_port and conn.status == psutil.CONN_LISTEN:
                pid = conn.pid
                if pid:
                    try:
                        p = psutil.Process(pid)
                        name = p.name().lower()
                        if "chrome" in name or "msedge" in name:
                            log.debug("发现占用端口 %d 的 %s (PID=%d)，终止中...", cdp_port, name, pid)
                            p.terminate()
                            p.wait(timeout=5)
                    except Exception:
                        pass
    except ImportError:
        # psutil 不可用，回退到 tasklist 方案
        try:
            out = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/FO", "CSV", "/NH"],
                                          text=True, errors="replace", timeout=10)
            if out.strip():
                log.warning("检测到 Chrome 进程已在运行，建议先关闭所有 Chrome 窗口再运行脚本")
        except Exception:
            pass
    except Exception:
        pass




# ============================================================
# 六、投票会话（封装"一个 profile 完成 N 次投票"）
# ============================================================
@dataclass
class VoteResult:
    profile_id: int
    seq: int                 # 该 profile 内第几票
    global_seq: int          # 全局第几票
    status: Optional[int]
    biz_ok: Optional[bool]
    ok: bool
    reason: str
    elapsed_ms: float
    attempts: int
    proxy: str = ""          # 当前使用的代理


class VoteSession:
    """
    封装一个独立 profile 的投票：
      - 启动 Chrome（隔离 user-data-dir + CDP 端口）
      - 连 CDP，开 page
      - 注入指纹（UA / viewport / 时区 / 语言）
      - 访问 vote_url 建立会话/CSRF
      - 在 profile 内连投 per_profile 票（每次填占位符，随机 choice）
      - 结束：关 CDP、杀进程、删 profile（除非 keep_profiles）
    """

    def __init__(self, index: int, cfg: VoteConfig, workdir: str,
                 action: Optional[ActionScript] = None):
        self.index = index
        self.cfg = cfg
        # workdir 可能是相对路径（如 .vote1000_work），Chrome 要求绝对路径
        self.workdir = os.path.abspath(workdir)
        self.action = action or ActionScript(
            vote_url=cfg.vote_url, submit_url=cfg.submit_url,
            method=cfg.method, content_type=cfg.content_type,
            data=cfg.data, success_field=cfg.success_field,
            success_value=cfg.success_value,
        )
        # 【修复】user_data_dir 必须传绝对路径给 Chrome，否则 Windows 上
        # 会出现"无法对其数据目录执行读写操作"
        self.user_data_dir = os.path.join(self.workdir, f"profile_{index:04d}")
        self.cdp_port = 9200 + (index % 20)    # 每 profile 唯一端口，错开避免占用冲突
        self._proc: Optional[subprocess.Popen] = None
        self._ws: Optional[WebSocket] = None
        self._chrome_path = ""
        self.results: List[VoteResult] = []
        self._session_token = ""

    # ---- 生命周期 ----
    def start(self) -> None:
        chrome = self.cfg.chrome_path or find_chrome()
        if not chrome:
            raise CDPError("未找到 Chrome/Edge。请用 --chrome 指定可执行路径，"
                           "或安装 Chrome/Edge 后重试。")
        self._chrome_path = chrome
        self._proc = launch_chrome(
            chrome, self.user_data_dir, self.cdp_port, self.cfg.headless,
            proxy=self.cfg.proxy or ""  # 传递代理给 Chrome
        )
        ws_url, _tid = wait_for_devtools(self.cdp_port, self.user_data_dir,
                                          timeout=40.0)
        self._ws = WebSocket(ws_url, timeout=self.cfg.timeout)
        # 【修复】Chrome 的 CDP 协议在 WebSocket 连接建立后还需要初始化时间
        log.debug("WebSocket 已连接，等待 CDP 协议初始化...")
        time.sleep(1.5)
        # 关键命令带重试，应对 Chrome 初始化期间的临时不可用
        self._cdp_with_retry("Page.enable", retries=3, delay=1.0)
        self._cdp_with_retry("Network.enable", retries=3, delay=1.0)

    def _cdp_with_retry(self, method: str, params: Optional[Dict] = None,
                        retries: int = 3, delay: float = 1.0) -> Dict:
        """带重试的 CDP 命令，解决 Chrome 刚启动时协议未就绪的问题。"""
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                log.debug("发送 CDP 命令（第 %d/%d 次）: %s", attempt, retries, method)
                return self._ws.send_command(method, params)
            except CDPError as e:
                last_err = e
                log.warning("CDP 命令 %s 第 %d 次失败: %s，%.1fs 后重试...",
                           method, attempt, e, delay)
                time.sleep(delay)
        raise CDPError(f"CDP 命令 {method} 在 {retries} 次重试后仍失败: {last_err}")

    def stop(self) -> None:
        if self._ws:
            try:
                self._ws.send_command("Browser.close")
            except Exception:
                pass
            self._ws.close()
            self._ws = None
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        if not self.cfg.keep_profiles:
            try:
                shutil.rmtree(self.user_data_dir, ignore_errors=True)
                log.debug("已删除 profile 目录: %s", self.user_data_dir)
            except Exception as e:
                log.debug("删 profile 失败（可忽略）: %s", e)

    # ---- 指纹 ----
    def _apply_fingerprint(self) -> None:
        cfg = self.cfg
        ua = pick_fp(cfg, "ua")
        vp = pick_fp(cfg, "viewport")
        tz = pick_fp(cfg, "tz")
        lang = pick_fp(cfg, "lang")
        w, h = (vp.split("x") if vp else ("1366", "768"))
        try:
            self._ws.send_command(
                "Emulation.setUserAgentOverride",
                {"userAgent": ua, "platform": "Win32", "acceptLanguage": lang,
                 "userAgentMetadata": {"brands": [], "fullVersionList": []}},
            )
            self._ws.send_command(
                "Emulation.setDeviceMetricsOverride",
                {"width": int(w), "height": int(h),
                 "deviceScaleFactor": 1, "mobile": False},
            )
            self._ws.send_command(
                "Emulation.setTimezoneOverride", {"timezoneId": tz},
            )
            log.debug("指纹已应用: ua=…%s vp=%s tz=%s lang=%s",
                      ua[-20:], vp, tz, lang)
        except Exception as e:
            log.debug("指纹应用部分失败（不影响投票）: %s", e)

    # ---- 页面操作 ----
    def _navigate(self, url: str, wait: float = 4.0) -> None:
        self._ws.send_command("Page.navigate", {"url": url})
        time.sleep(wait)

    def _run_js(self, expression: str) -> Any:
        r = self._ws.send_command(
            "Runtime.evaluate", {"expression": expression, "returnByValue": True}
        )
        return r.get("result", {}).get("value")

    def _collect_csrf(self, url: str) -> Dict[str, str]:
        """访问投票页后，从 cookie / meta 里抓 CSRF / token，拼进后续提交头。"""
        headers_extra: Dict[str, str] = {}
        try:
            cookies = self._ws.send_command("Network.getCookies", {"urls": [url]})
            ck = {}
            for c in cookies.get("cookies", []):
                ck[c["name"].lower()] = c["value"]
            for key in ("csrf", "csrf_token", "x-csrf-token", "_token", "token"):
                if key in ck:
                    headers_extra["X-CSRF-Token"] = ck[key]
                    break
            # 同时取页面里的 meta（常见 PHP CSRF）
            meta = self._run_js(
                "(function(){var m=document.querySelector('meta[name=csrf-token],meta[name=_token]');"
                "return m?m.content:'';})()"
            )
            if meta:
                headers_extra["X-CSRF-Token"] = meta
        except Exception as e:
            log.debug("抓 CSRF 失败（可能无 CSRF）: %s", e)
        self._cookie_header = self._cookie_string()
        return headers_extra

    def _cookie_string(self) -> str:
        try:
            url = self.cfg.vote_url
            cookies = self._ws.send_command("Network.getCookies", {"urls": [url]})
            return "; ".join(f'{c["name"]}={c["value"]}' for c in cookies.get("cookies", []))
        except Exception:
            return ""

    # ---- 核心：在浏览器上下文里发一次提交（携带真实 cookie/csrf）----
    def _one_submit(self, ctx: Dict[str, Any]) -> VoteResult:
        cfg = self.cfg
        choice = random.choice(self.action.choice_values) if self.action.choice_values else "1"
        ctx = {**ctx, "choice": choice}
        body = fill_template(self.action.data, ctx)
        try:
            body = json.loads(body)
            data_json = json.dumps(body)
        except Exception:
            data_json = body

        # 在页面 JS 上下文里 fetch（自动带 cookie、走同源，最像真人）
        extra_headers = self._collect_csrf(self.action.vote_url)
        hjson = json.dumps({**{"Content-Type": self.action.content_type},
                            **extra_headers})
        fetch_js = f"""
        (async function(){{
          const opts={{
            method: {json.dumps(self.action.method.upper())},
            headers: {hjson},
            body: {json.dumps(data_json)}
          }};
          const r = await fetch({json.dumps(self.action.submit_url)}, opts);
          const text = await r.text();
          return {{status: r.status, body: text}};
        }})()
        """
        t0 = time.monotonic()
        r = self._ws.send_command(
            "Runtime.evaluate",
            {"expression": fetch_js, "awaitPromise": True, "returnByValue": True},
        )
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        val = r.get("result", {}).get("value") or {}
        status = val.get("status")
        text = val.get("body", "") or ""
        biz = self._judge_biz(text)
        ok = (status is not None and 200 <= status < 300) and biz is not False
        reason = ""
        if not ok:
            try:
                j = json.loads(text)
                reason = str(j.get("msg") or j.get("message") or j.get("error") or j)[:120]
            except Exception:
                reason = text[:120] or f"HTTP {status}"
        return VoteResult(
            profile_id=self.index, seq=len(self.results) + 1,
            global_seq=0, status=status, biz_ok=biz, ok=ok,
            reason=reason, elapsed_ms=elapsed_ms, attempts=1,
        )

    def _judge_biz(self, text: str) -> Optional[bool]:
        if not self.action.success_field:
            return None
        try:
            obj = json.loads(text)
        except Exception:
            return None
        cur: Any = obj
        try:
            for key in self.action.success_field.split("."):
                cur = cur[key]
        except Exception:
            return False
        if self.action.success_value != "":
            want = self.action.success_value.lower()
            got = ("true" if cur else "false") if isinstance(cur, bool) else str(cur).lower()
            return got == want
        return bool(cur)

    # ---- 单 profile 内连投 ----
    def vote_batch(self, count: Optional[int] = None) -> List[VoteResult]:
        """本 profile 内连投 N 票。count 为空则用 cfg.per_profile。"""
        cfg = self.cfg
        n = count if count is not None else cfg.per_profile
        # 打开投票页建立会话
        self._apply_fingerprint()
        self._navigate(self.action.vote_url, wait=3.0)

        results: List[VoteResult] = []
        for i in range(n):
            if not self._ws:
                break
            ctx = {"uuid": uuid.uuid4().hex, "ts": int(time.time()),
                   "seq": len(results) + 1, "rand": random.randint(1000, 9999)}
            # 轻量选择/点击动作（可选）
            for sel, val in self.action.pre_select.items():
                self._run_js(f"document.querySelector({json.dumps(sel)}).value={json.dumps(fill_template(val, ctx))};")
            for sel in self.action.pre_click:
                self._run_js(f"document.querySelector({json.dumps(sel)}).click();")

            res = self._one_submit(ctx)
            self.results.append(res)
            results.append(res)
            if cfg.stop_on_fail and not res.ok:
                log.warning("profile#%d 第%d票失败（%s），stop_on_fail 生效，提前结束本 profile",
                            self.index, res.seq, res.reason)
                break
            if len(results) < n:
                time.sleep(cfg.between_vote_delay)
        return results


# ============================================================
# 七、编排器：跨 profile 轮换直到 total_votes
# ============================================================
class VoteOrchestrator:
    def __init__(self, cfg: VoteConfig, workdir: str,
                 action: Optional[ActionScript] = None):
        self.cfg = cfg
        # workdir 可能是相对路径，统一转绝对路径
        self.workdir = os.path.abspath(workdir)
        self.action = action
        os.makedirs(self.workdir, exist_ok=True)
        self._session_count = 0    # 实际创建的会话数
        self.global_votes = 0
        self.success = 0
        self.failed = 0
        self.biz_fail = 0
        self.all_results: List[VoteResult] = []
        self._session_factory: Optional[callable] = None   # 由驱动注入

    def _make_session(self) -> "VoteSession":
        self._session_count += 1
        if self._session_factory is not None:
            return self._session_factory(self._session_count)
        return VoteSession(self._session_count, self.cfg, self.workdir, self.action)

    def run(self) -> None:
        cfg = self.cfg
        log.info("目标 %d 票，每 profile %d 票，预计 %d 个 profile",
                 cfg.total_votes, cfg.per_profile,
                 (cfg.total_votes + cfg.per_profile - 1) // cfg.per_profile)
        while self.global_votes < cfg.total_votes:
            remaining = cfg.total_votes - self.global_votes
            n_this = min(cfg.per_profile, remaining)
            sess = self._make_session()
            try:
                sess.start()
            except CDPError as e:
                log.error("profile#%d 启动失败：%s（跳过并换新 profile）",
                          sess.index, e)
                sess.stop()
                continue
            try:
                got = sess.vote_batch(count=n_this)
                for res in got:
                    self.global_votes += 1
                    res.global_seq = self.global_votes
                    self.all_results.append(res)
                    if res.ok:
                        self.success += 1
                    else:
                        self.failed += 1
                        if res.biz_ok is False:
                            self.biz_fail += 1
                    self._progress(res)
            except Exception as e:
                log.error("profile#%d 投票过程异常：%s", sess.index, e)
                self.failed += n_this - len(sess.results)
            finally:
                sess.stop()
            # profile 间隔
            if self.global_votes < cfg.total_votes:
                time.sleep(cfg.between_profile_delay)

    def _progress(self, res: VoteResult) -> None:
        total = self.cfg.total_votes
        pct = self.global_votes / total
        bar = "#" * int(20 * pct) + "-" * int(20 * (1 - pct))
        proxy_info = f" proxy={res.proxy}" if res.proxy else ""
        log.info("  [%s] %5d/%d  P%d  第%d票 status=%s ok=%s%s%s",
                 bar, self.global_votes, total,
                 res.profile_id, res.seq, res.status, res.ok,
                 proxy_info,
                 res.reason if not res.ok else " ✓")

    def summary(self) -> Dict[str, Any]:
        return {
            "total_voted": self.global_votes,
            "success": self.success,
            "failed": self.failed,
            "biz_fail": self.biz_fail,
            "profiles_used": self._session_count,
            "results": [asdict(r) for r in self.all_results],
        }

    def write_out(self, path: str) -> None:
        ext = os.path.splitext(path)[1].lower()
        s = self.summary()
        if ext == ".csv":
            import csv as _csv
            cols = ["global_seq", "profile_id", "seq", "status", "biz_ok",
                    "ok", "attempts", "elapsed_ms", "reason", "proxy"]
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = _csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                for r in s["results"]:
                    w.writerow({c: r.get(c, "") for c in cols})
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(s, f, ensure_ascii=False, indent=2)
        log.info("结果已写入 %s", path)


def _build_session(index: int, cfg: VoteConfig, action: ActionScript,
                   workdir: str, driver: str):
    """按驱动类型构造会话对象（统一入口）。

    driver:
      http       → HttpVoteSession（纯 HTTP，不弹任何浏览器窗口，最快）
      playwright → PlaywrightVoteSession（需要装 playwright）
      cdp/其它   → VoteSession（启动真实 Chrome/Edge + CDP）
    """
    if driver == "http":
        return HttpVoteSession(index, cfg, workdir, action)
    if driver == "playwright":
        return PlaywrightVoteSession(index, cfg, action)
    return VoteSession(index, cfg, workdir, action)


def _make_session_with_flclash(index: int, cfg: VoteConfig, action: ActionScript,
                               flclash: FlClashController,
                               workdir: str = ".vote1000_work",
                               driver: str = "cdp"):
    """创建 session 并在启动前切换一次 FlClash 节点。

    注意：这里同样尊重 driver —— 若 driver="http"，换节点后仍用纯 HTTP 会话，
    不会因为开了节点轮换就强行去启动浏览器。
    """
    # 先切换节点
    flclash.switch_next()
    time.sleep(1.5)  # 给 FlClash 一点时间切换
    return _build_session(index, cfg, action, workdir, driver)



# ============================================================
# 八、Playwright 驱动（可选，更稳）
# ============================================================
def _maybe_playwright(cfg: VoteConfig) -> Optional[str]:
    """尝试加载 playwright，可用返回 'playwright'。"""
    try:
        from playwright.sync_api import sync_playwright  # noqa
        return "playwright"
    except Exception:
        return None


class PlaywrightVoteSession:
    """用 Playwright 的一个 context 完成 N 票（每个 context 即一个隔离身份）。"""

    def __init__(self, index: int, cfg: VoteConfig, action: ActionScript):
        self.index = index
        self.cfg = cfg
        self.action = action
        self.results: List[VoteResult] = []
        self._pw = None
        self._browser = None
        self._ctx = None
        self._page = None

    def start(self) -> None:
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.cfg.headless,
            args=["--disable-background-networking"],
        )
        # 每个 context 一份独立 user-data-dir + 随机指纹
        # 【修复】转为绝对路径，避免 Playwright 在相对路径下出错
        profile_dir = os.path.abspath(
            os.path.join(f".pw_profiles", f"profile_{self.index:04d}")
        )
        os.makedirs(profile_dir, exist_ok=True)
        vp = pick_fp(self.cfg, "viewport").split("x")
        tz = pick_fp(self.cfg, "tz")
        lang = pick_fp(self.cfg, "lang")
        ua = pick_fp(self.cfg, "ua")
        self._ctx = self._browser.new_context(
            user_data_dir=profile_dir,
            user_agent=ua,
            locale=lang,
            timezone_id=tz,
            viewport={"width": int(vp[0]), "height": int(vp[1])} if len(vp) == 2 else None,
        )
        self._page = self._ctx.new_page()

    def _one_submit(self, ctx_vars: Dict[str, Any]) -> VoteResult:
        choice = random.choice(self.action.choice_values) if self.action.choice_values else "1"
        cvars = {**ctx_vars, "choice": choice}
        body = fill_template(self.action.data, cvars)
        t0 = time.monotonic()
        resp = self._page.request.fetch(
            self.action.submit_url,
            method=self.action.method.upper(),
            data=body,
            headers={"Content-Type": self.action.content_type},
            timeout=self.cfg.timeout * 1000,
        )
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        status = resp.status
        text = resp.text()
        biz = self._judge_biz(text)
        ok = (200 <= status < 300) and biz is not False
        reason = ""
        if not ok:
            try:
                j = json.loads(text)
                reason = str(j.get("msg") or j.get("message") or j.get("error") or j)[:120]
            except Exception:
                reason = text[:120] or f"HTTP {status}"
        return VoteResult(self.index, len(self.results) + 1, 0, status, biz, ok,
                          reason, elapsed_ms, 1)

    def _judge_biz(self, text: str) -> Optional[bool]:
        if not self.action.success_field:
            return None
        try:
            obj = json.loads(text)
        except Exception:
            return None
        cur: Any = obj
        try:
            for key in self.action.success_field.split("."):
                cur = cur[key]
        except Exception:
            return False
        if self.action.success_value != "":
            want = self.action.success_value.lower()
            got = ("true" if cur else "false") if isinstance(cur, bool) else str(cur).lower()
            return got == want
        return bool(cur)

    def vote_batch(self, count: Optional[int] = None) -> List[VoteResult]:
        n = count if count is not None else self.cfg.per_profile
        self._page.goto(self.action.vote_url, timeout=self.cfg.timeout * 1000)
        out = []
        for i in range(n):
            ctx = {"uuid": uuid.uuid4().hex, "ts": int(time.time()), "seq": i + 1}
            r = self._one_submit(ctx)
            self.results.append(r)
            out.append(r)
            if self.cfg.stop_on_fail and not r.ok:
                break
            if i < n - 1:
                time.sleep(self.cfg.between_vote_delay)
        return out

    def stop(self) -> None:
        for a in ("_ctx", "_browser", "_pw"):
            obj = getattr(self, a, None)
            if obj:
                try:
                    obj.close() if a != "_pw" else obj.stop()
                except Exception:
                    pass
                setattr(self, a, None)


# ============================================================
# 八.5、HTTP 降级驱动（无需浏览器；每个"身份"用独立 Cookie 文件）
# ============================================================
class HttpVoteSession:
    """
    无浏览器降级版：每个 profile 用一份独立 Cookie（cookie 文件）代表一个"浏览器"，
    投满 per_profile 票后删 Cookie 文件换新。适用于目标接口是纯表单/JSON POST、
    不校验 TLS 指纹/CANVAS 等浏览器指纹的场景。速度最快。
    """

    def __init__(self, index: int, cfg: VoteConfig, workdir: str,
                 action: ActionScript):
        self.index = index
        self.cfg = cfg
        # workdir 可能是相对路径，统一转绝对路径
        self.workdir = os.path.abspath(workdir)
        self.action = action
        self.cookie_file = os.path.join(self.workdir, f"identity_{index:04d}.cookie")
        self.results: List[VoteResult] = []
        os.makedirs(workdir, exist_ok=True)
        # 该 session 的"浏览器身份"（start() 时一次性生成，整个 session 内保持不变）
        self._cookie = ""
        self._ua = ""
        self._lang = ""
        self._proxy = ""          # 当前 session 使用的代理
        self._use_requests = False
        self._session = None
        self._opener = None
        # 优先使用 requests（支持 SOCKS5），回退到 urllib
        try:
            import requests as _rq
            self._requests = _rq
            self._use_requests = True
        except ImportError:
            self._requests = None

    # ---- 身份（每个 session 一个，整段不变，像一个真实浏览器）----
    def _make_identity(self) -> None:
        self._cookie = f"PHPSESSID={uuid.uuid4().hex[:16]}"
        self._ua = pick_fp(self.cfg, "ua") or "Mozilla/5.0"
        self._lang = pick_fp(self.cfg, "lang") or "zh-CN"

    def _get_headers(self) -> Dict[str, str]:
        """预热用 GET 头。"""
        return {
            "User-Agent": self._ua,
            "Accept-Language": self._lang,
            "Cookie": self._cookie,
        }

    def _headers(self) -> Dict[str, str]:
        """提交用 POST 头（UA/语言/Cookie 整段 session 不变）。"""
        return {
            "Content-Type": self.action.content_type,
            "Cookie": self._cookie,
            "User-Agent": self._ua,
            "Accept-Language": self._lang,
            "Referer": self.action.vote_url,
        }

    def start(self) -> None:
        # 每次 start() 生成全新身份（cookie + UA + 语言），这就是"换浏览器"的核心
        self._make_identity()
        self._write_cookie()
        # 选择代理：proxy_list 轮换 或 单个 proxy
        if self.cfg.proxy_list:
            self._proxy = self.cfg.proxy_list[(self.index - 1) % len(self.cfg.proxy_list)]
        else:
            self._proxy = self.cfg.proxy or ""
        if self._use_requests:
            self._session = self._build_requests_session(self._proxy)
            if self.cfg.http_warmup:
                self._warmup()
        else:
            self._opener = self._build_opener(self._proxy)
            if self.cfg.http_warmup:
                self._warmup_urllib()

    def _warmup(self) -> None:
        """预热：先 GET 投票页，建立会话 / 拿 CSRF Cookie（失败不致命）。"""
        try:
            self._session.get(self.action.vote_url, headers=self._get_headers(),
                              timeout=self.cfg.timeout, allow_redirects=True)
        except Exception as e:
            log.debug("HTTP 预热失败（忽略）：%s", e)

    def _warmup_urllib(self) -> None:
        try:
            req = urllib.request.Request(self.action.vote_url, headers=self._get_headers())
            with self._opener.open(req, timeout=self.cfg.timeout):
                pass
        except Exception as e:
            log.debug("HTTP 预热失败（忽略）：%s", e)

    def stop(self) -> None:
        if not self.cfg.keep_profiles:
            try:
                if os.path.isfile(self.cookie_file):
                    os.remove(self.cookie_file)
            except Exception:
                pass
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None

    @staticmethod
    def _build_opener(proxy: str = ""):
        if proxy:
            p = urllib.parse.urlparse(proxy)
            scheme = p.scheme or "http"
            host = p.hostname or "127.0.0.1"
            port = p.port or 7890
            proxy_url = f"{scheme}://{host}:{port}"
            handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
            return urllib.request.build_opener(handler)
        return urllib.request.build_opener()

    def _build_requests_session(self, proxy: str = ""):
        """创建 requests.Session，配置代理（支持 http/https/socks5）。"""
        session = self._requests.Session()
        if proxy:
            # requests 的 proxies 字典支持 http/https/socks5
            session.proxies = {
                "http": proxy,
                "https": proxy,
            }
        return session

    def _write_cookie(self) -> None:
        with open(self.cookie_file, "w", encoding="utf-8") as f:
            f.write(self._cookie)

    def _one_submit(self, ctx: Dict[str, Any]) -> VoteResult:
        choice = random.choice(self.action.choice_values) if self.action.choice_values else "1"
        cvars = {**ctx, "choice": choice}
        body = fill_template(self.action.data, cvars).encode("utf-8")
        t0 = time.monotonic()
        status, text = None, ""
        try:
            if self._use_requests:
                status, text = self._submit_with_requests(body)
            else:
                status, text = self._submit_with_urllib(body)
        except Exception as e:
            status = 0
            text = f"{type(e).__name__}: {e}"
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        biz = self._judge_biz(text)
        ok = (status is not None and 200 <= status < 300) and biz is not False
        reason = ""
        if not ok:
            try:
                j = json.loads(text)
                reason = str(j.get("msg") or j.get("message") or j.get("error") or j)[:120]
            except Exception:
                reason = text[:120] or f"HTTP {status}"
        return VoteResult(self.index, len(self.results) + 1, 0, status, biz, ok,
                          reason, elapsed_ms, 1, proxy=self._proxy)

    def _submit_with_urllib(self, body: bytes):
        """使用 urllib 发送请求（仅支持 HTTP 代理）。"""
        req = urllib.request.Request(
            self.action.submit_url,
            data=body,
            method=self.action.method.upper(),
            headers=self._headers(),
        )
        status, text = None, ""
        try:
            with self._opener.open(req, timeout=self.cfg.timeout) as r:
                status = r.status
                text = r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            status = e.code
            text = e.read().decode("utf-8", errors="replace")
        return status, text

    def _submit_with_requests(self, body: bytes):
        """使用 requests 发送请求（支持 HTTP/HTTPS/SOCKS5 代理）。"""
        resp = self._session.request(
            self.action.method.upper(),
            self.action.submit_url,
            data=body,
            headers=self._headers(),
            timeout=self.cfg.timeout,
        )
        return resp.status_code, resp.text

    def _judge_biz(self, text: str) -> Optional[bool]:
        if not self.action.success_field:
            return None
        try:
            obj = json.loads(text)
        except Exception:
            return None
        cur: Any = obj
        try:
            for key in self.action.success_field.split("."):
                cur = cur[key]
        except Exception:
            return False
        if self.action.success_value != "":
            want = self.action.success_value.lower()
            got = ("true" if cur else "false") if isinstance(cur, bool) else str(cur).lower()
            return got == want
        return bool(cur)

    def vote_batch(self, count: Optional[int] = None) -> List[VoteResult]:
        n = count if count is not None else self.cfg.per_profile
        out = []
        for i in range(n):
            ctx = {"uuid": uuid.uuid4().hex, "ts": int(time.time()),
                   "seq": i + 1, "rand": random.randint(1000, 9999)}
            r = self._one_submit(ctx)
            self.results.append(r)
            out.append(r)
            if self.cfg.stop_on_fail and not r.ok:
                break
            if i < n - 1:
                time.sleep(self.cfg.between_vote_delay)
        return out


# ============================================================
# 九、CLI
# ============================================================
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="自动轮换浏览器 profile 投票工具（突破单浏览器 10 次上限）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    g = p.add_argument_group("目标")
    g.add_argument("--vote-url", default="", help="投票页 URL")
    g.add_argument("--submit-url", default="", help="提交投票的接口 URL")
    g.add_argument("--method", default="POST")
    g.add_argument("--data", default="", help="原始请求体（表单/JSON，可用 {{choice}}/{{ts}}/{{uuid}} 占位符）")
    g.add_argument("--content-type", default="application/x-www-form-urlencoded")
    g.add_argument("--success-field", default="success")
    g.add_argument("--success-value", default="true")
    g.add_argument("--choice-values", default="", help="逗号分隔，每次投票随机取一个，如 1,2,3")
    g.add_argument("--action-file", default="", help="动作脚本 JSON 路径（推荐，最贴合真实流程）")

    g2 = p.add_argument_group("数量与节奏")
    g2.add_argument("--votes", type=int, default=1000, help="总票数（默认 1000）")
    g2.add_argument("--per-profile", type=int, default=10, help="每个 profile 投多少票（=单浏览器上限）")
    g2.add_argument("--between-vote-delay", type=float, default=1.0, help="同 profile 内两票间隔(秒)")
    g2.add_argument("--between-profile-delay", type=float, default=2.0, help="换 profile 间隔(秒)")
    g2.add_argument("--timeout", type=float, default=20.0, help="单次请求超时(秒)")
    g2.add_argument("--stop-on-fail", action="store_true", help="某票失败立即停，避免重复投")

    g3 = p.add_argument_group("驱动")
    g3.add_argument("--driver", default="http", choices=["auto", "cdp", "playwright", "http"],
                    help="驱动（默认 http：纯请求、不弹浏览器；cdp/playwright 才开真实浏览器）")
    g3.add_argument("--chrome", default="", help="Chrome/Edge 可执行路径（留空自动探测）")
    g3.add_argument("--headless", action="store_true", help="无头模式（仅浏览器驱动用）")
    g3.add_argument("--http-warmup", action="store_true",
                    help="HTTP 模式下先 GET 投票页预热（建立会话/拿 CSRF Cookie）")
    g3.add_argument("--no-random", action="store_true", help="关闭指纹随机化（固定指纹）")
    g3.add_argument("--keep-profiles", action="store_true", help="保留 profile 目录便于排查")
    g3.add_argument("--workdir", default="", help="profile 工作目录（默认 .vote1000_work）")

    g3b = p.add_argument_group("代理 / IP 轮换")
    g3b.add_argument("--proxy", default="", help="单个代理，如 http://127.0.0.1:7890")
    g3b.add_argument("--proxy-list", default="", help="代理列表文件（每行一个代理），自动轮换")
    g3b.add_argument("--flclash-api", default="", help="FlClash/草莓云 API 地址，如 http://127.0.0.1:9090")
    g3b.add_argument("--flclash-proxy-group", default="GLOBAL", help="FlClash 代理组名（默认 GLOBAL）")
    g3b.add_argument("--flclash-switch-on-profile", action="store_true",
                     help="每个 profile 自动切换到下一个节点（需开启 FlClash external-controller）")

    g4 = p.add_argument_group("输出")
    g4.add_argument("--out", default="vote1000_result.json", help="结果输出文件（.csv/.json）")
    g4.add_argument("--quiet", action="store_true", help="安静模式，少打日志")
    return p.parse_args()


def build_config(args: argparse.Namespace):
    choice_values = [c.strip() for c in args.choice_values.split(",") if c.strip()] or ["1"]
    action = None
    if args.action_file:
        action = ActionScript.load(args.action_file)
        # 命令行可覆盖 action 里的可选项
        if args.choice_values:
            action.choice_values = choice_values
    else:
        if not (args.vote_url and args.submit_url):
            raise SystemExit("✗ 必须提供 --vote-url 和 --submit-url，或 --action-file")
        action = ActionScript(
            vote_url=args.vote_url, submit_url=args.submit_url,
            method=args.method, content_type=args.content_type,
            data=args.data, success_field=args.success_field,
            success_value=args.success_value, choice_values=choice_values,
        )
    # 代理列表
    proxy_list = []
    if args.proxy_list and os.path.isfile(args.proxy_list):
        with open(args.proxy_list, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    proxy_list.append(line)
    cfg = VoteConfig(
        vote_url=action.vote_url, submit_url=action.submit_url,
        method=action.method, data=action.data,
        content_type=action.content_type,
        success_field=action.success_field, success_value=action.success_value,
        total_votes=args.votes, per_profile=args.per_profile,
        between_vote_delay=args.between_vote_delay,
        between_profile_delay=args.between_profile_delay,
        timeout=args.timeout,
        randomize_fingerprint=not args.no_random,
        driver=args.driver, chrome_path=args.chrome,
        headless=args.headless, out=args.out,
        stop_on_fail=args.stop_on_fail, keep_profiles=args.keep_profiles,
        proxy=args.proxy,
        proxy_list=proxy_list,
        flclash_api=args.flclash_api,
        flclash_proxy_group=args.flclash_proxy_group,
        flclash_switch_on_profile=args.flclash_switch_on_profile,
        http_warmup=args.http_warmup,
    )
    return cfg, action


def resolve_driver(cfg: VoteConfig) -> str:
    if cfg.driver != "auto":
        return cfg.driver
    # auto：默认走纯 HTTP（不弹浏览器、最快）。
    # 如需真实浏览器，请显式指定 --driver cdp 或 --driver playwright。
    return "http"


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        cfg, action = build_config(args)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2

    driver = resolve_driver(cfg)
    log.info("版本 %s", __BUILD__)
    log.info("驱动=%s  目标=%d 票 / 每 profile %d 票  指纹随机=%s  无头=%s",
             driver, cfg.total_votes, cfg.per_profile,
             cfg.randomize_fingerprint, cfg.headless)
    if driver == "http":
        log.info("HTTP 模式：纯请求投票，不会启动任何浏览器窗口。")
    if cfg.proxy_list:
        log.info("IP 轮换：已加载 %d 个代理，每 profile 自动切换", len(cfg.proxy_list))
    elif cfg.proxy:
        log.info("使用代理：%s", cfg.proxy)

    # FlClash/草莓云 自动节点轮换（可选）
    flclash: Optional[FlClashController] = None
    if cfg.flclash_api:
        flclash = FlClashController(cfg.flclash_api, cfg.flclash_proxy_group)
        if flclash.available:
            log.info("[FlClash] API 已连接，代理组=%s，可用节点=%d",
                     cfg.flclash_proxy_group, len(flclash._node_list))
            if cfg.flclash_switch_on_profile:
                log.info("[FlClash] 每个 profile 自动切换一次节点")
        else:
            log.warning("[FlClash] API 连接失败（%s 无响应），将不切换节点。", cfg.flclash_api)
            log.warning("  如需自动换 IP：在草莓云/FlClash 设置中开启「外部控制 / External "
                        "Controller」并设为 127.0.0.1:9090，重启草莓云后再运行本脚本。")
            log.warning("  或：将草莓云设为「自动选择/负载均衡」模式，本脚本仍走 127.0.0.1:7890 由草莓云内部轮换。")
            flclash = None

    workdir = args.workdir or ".vote1000_work"
    orch = VoteOrchestrator(cfg, workdir, action)

    if flclash and cfg.flclash_switch_on_profile:
        orch._session_factory = lambda i: _make_session_with_flclash(
            i, cfg, action, flclash, orch.workdir, driver)
    else:
        orch._session_factory = lambda i: _build_session(
            i, cfg, action, workdir, driver)

    orch.run()

    s = orch.summary()
    log.info("=" * 56)
    log.info("完成：投 %d/%d 票  成功 %d  失败 %d  业务失败 %d  用了 %d 个 profile",
             s["total_voted"], cfg.total_votes, s["success"], s["failed"],
             s["biz_fail"], s["profiles_used"])
    log.info("=" * 56)
    orch.write_out(args.out)
    print(f"\n结果已写入 {args.out}")

    if s["total_voted"] < cfg.total_votes:
        return 4
    if s["failed"] == 0:
        return 0
    return 3


# ============================================================
# 十、Spyder / Jupyter 配置模式（改下面变量 → 按 F5）
# ============================================================
# 不用命令行引号，直接在 Spyder 里改 SPYDR_CONFIG，然后按 F5 运行。
# 三种运行模式：
#   MODE = "mock"   本地起 mock 投票服务，跑 1000 票自测（不碰真实站点，最安全）
#   MODE = "local"  指向你本机起的服务（如 127.0.0.1:8000）
#   MODE = "real"   指向真实投票站点（请仅用于已授权环境）
SPYDR_CONFIG = {
    # ---- 运行模式：mock / local / real ----
    #   mock  → 本地起 mock 服务，1000 票自测（不碰真实站点，最安全）
    #   local → 指向本机服务（如 127.0.0.1:8000）
    #   real  → 指向真实投票站点（仅用于已授权测试环境）
    #   下面已改为 real 模式，指向你的测试环境。
    "MODE": "real",

    # ---- ⚠️ dry_run：先只发 1 次请求验证配置（强烈建议先保持 True）----
    #   True  → 只发 1 次请求，打印完整诊断（状态码 / 响应内容 / 下一步建议），
    #           不批量投票。确认 status=200 且业务成功后，再改 False 跑批量。
    #   False → 正常批量投票。
    "dry_run": False,

    # ---- 自动探测候选接口（submit_url 404 时很有用）----
    #   True → 投票前先 GET 抓取 vote_url 页面源码，扫描里面的候选接口路径，
    #          逐个探测并报告哪个不是 404。结果仅供参考，最终以 F12 抓包为准。
    "auto_probe": False,

    # ---- 代理 / IP 轮换 ----
    #   HTTP 模式下，所有请求都经此代理发出（草莓云本地端口）
    #   格式：http://127.0.0.1:7890 或 socks5://127.0.0.1:7890
    "proxy": "http://127.0.0.1:7890",
    "proxy_list": "",

    # ---- 草莓云/FlClash 自动节点轮换 ----
    #   True  = 每个身份换一次节点（换 IP）；需草莓云开启 external-controller。
    #           API 没开时自动降级（只警告，不影响运行）。
    "flclash_api": "http://127.0.0.1:9090",
    "flclash_proxy_group": "GLOBAL",
    "flclash_switch_on_profile": True,

    # ---- 目标（你的测试环境）----
    #   如需恢复 mock 自测，将 MODE 改回 "mock" 即可。
    "vote_url": "https://pvd.rt25.luzhangtong.com/detail.php?id=19&activity_id=2&rank=47&_r=1",
    "submit_url": "https://pvd.rt25.luzhangtong.com/api/vote.php",
    "method": "POST",
    "data": "activity_id=2&participant_id=19&openid=",
    "content_type": "application/x-www-form-urlencoded",
    "success_field": "code",
    "success_value": "1",
    "choice_values": ["1"],

    # ---- 数量与节奏（1000 票 = 每身份 10 票 × 100 个身份）----
    "votes": 10,  # 先测试 20 票
    "per_profile": 10,
    "between_vote_delay": 0.5,       # 同身份内两票间隔（秒）
    "between_profile_delay": 1.0,    # 换身份间隔（秒）
    "timeout": 20.0,

    # ---- 驱动：http / cdp / playwright / auto ----
    #  默认 http：纯 HTTP 请求投票，不弹任何浏览器窗口，最快。
    #  每个身份自动换 cookie + UA + 语言，等价于"换一个浏览器"。
    #  如需真实浏览器（目标站校验 CANVAS/WebGL 时），改成 "cdp" 或 "playwright"。
    "driver": "http",
    "headless": False,               # 仅浏览器驱动用
    "chrome": "",                    # 仅浏览器驱动用，留空自动探测
    "http_warmup": False,            # True=每个身份先 GET 投票页预热（建立会话）

    # ---- 输出 ----
    "stop_on_fail": False,
    "keep_profiles": False,
    "out": "vote1000_result.json",
    "workdir": ".vote1000_work",
}


def _run_in_spyder() -> int:
    """Spyder / Jupyter 入口：按 F5 时走这里（无命令行参数）。"""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%H:%M:%S")
    print(f"[版本] {__BUILD__}")
    c = dict(SPYDR_CONFIG)
    mode = c.pop("MODE", "mock").lower()
    dry_run = bool(c.pop("dry_run", False))
    auto_probe = bool(c.pop("auto_probe", False))

    # ---- real/local 模式：先自动探测候选接口（如果 submit_url 是 404）----
    if mode in ("real", "local") and auto_probe:
        import urllib.request, urllib.error
        base = c["submit_url"]
        # 候选路径模式（从实际站点常见命名推断）
        candidates = []
        # 1. 从 vote_url 提取 host
        from urllib.parse import urlparse
        host = urlparse(c["vote_url"]).netloc
        # 2. 扫描 HTML 里 /xxx/vote 之类路径（可选，简化：先给几个常见后缀）
        for path in ["/ajax/vote", "/api/vote", "/vote.php", "/api/vote.php",
                     "/index.php?c=vote&a=vote", "/index.php?m=vote&a=submit"]:
            candidates.append(f"https://{host}{path}")
        # 3. 逐个探测
        print("\n" + "=" * 56)
        print("自动探测候选接口（仅供参考，最终以 F12 抓包为准）：")
        found = []
        for url in candidates:
            try:
                req = urllib.request.Request(url, method="POST",
                    headers={"User-Agent": "Mozilla/5.0", "Content-Type": c["content_type"]})
                with urllib.request.urlopen(req, timeout=10) as r:
                    status = r.status
                if status != 404:
                    found.append((url, status))
                    print(f"  ✓ {url} -> {status}")
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    found.append((url, e.code))
                    print(f"  ! {url} -> {e.code}")
            except Exception as e:
                pass
        if found:
            print(f"\n推荐使用（非 404）：{found[0][0]}")
            print("=" * 56 + "\n")
        else:
            print("未找到非 404 的候选路径，请手动用 F12 抓包。")
            print("=" * 56 + "\n")

    # ---- dry_run：只发 1 次请求验证配置 ----
    if dry_run and mode in ("real", "local"):
        import urllib.request, urllib.error
        print("\n" + "=" * 56)
        print("dry_run 模式：只发 1 次请求验证配置（不批量投票）")
        print("=" * 56)
        print(f"  vote_url   = {c['vote_url']}")
        print(f"  submit_url = {c['submit_url']}")
        print(f"  method     = {c['method']}")
        print(f"  data       = {c['data'][:100]}{'...' if len(c['data'])>100 else ''}")
        print(f"  timeout    = {c['timeout']}s")
        if c.get("proxy"):
            print(f"  proxy      = {c['proxy']}")
        elif c.get("proxy_list"):
            print(f"  proxy_list = {c['proxy_list']}")
        print()
        # 构造请求
        body = fill_template(c["data"], {"choice": c["choice_values"][0] if c["choice_values"] else "1",
                                        "ts": int(time.time()), "uuid": uuid.uuid4().hex,
                                        "rand": random.randint(1000, 9999)}).encode("utf-8")
        req = urllib.request.Request(
            c["submit_url"],
            data=body,
            method=c["method"],
            headers={
                "Content-Type": c["content_type"],
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
                "Referer": c["vote_url"],
            },
        )
        # 使用代理（优先 requests 支持 SOCKS5，否则 urllib）
        t0 = time.time()
        status, resp_text, elapsed = None, "", 0.0
        proxy = c.get("proxy", "") or ""
        try:
            # 优先 requests（支持 SOCKS5）
            try:
                import requests as _rq
                proxies = {"http": proxy, "https": proxy} if proxy else None
                headers = {
                    "Content-Type": c["content_type"],
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
                    "Referer": c["vote_url"],
                }
                resp = _rq.request(
                    c["method"], c["submit_url"],
                    data=body, headers=headers,
                    proxies=proxies, timeout=float(c["timeout"]),
                )
                status = resp.status_code
                resp_text = resp.text
            except ImportError:
                # 回退到 urllib
                opener = HttpVoteSession._build_opener(proxy)
                with opener.open(req, timeout=float(c["timeout"])) as r:
                    status = r.status
                    resp_text = r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            status = e.code
            resp_text = e.read().decode("utf-8", errors="replace")
        except Exception as e:
            status = 0
            resp_text = f"{type(e).__name__}: {e}"
        elapsed = (time.time() - t0) * 1000

        # 打印诊断
        print(f"  → 请求已发出")
        print(f"  → HTTP 状态码: {status}")
        print(f"  → 耗时: {elapsed:.0f} ms")
        print(f"  → 响应内容前 300 字符:")
        print("    " + resp_text[:300].replace("\n", " ")[:200])
        print()

        # 判断业务成功
        biz_ok = None
        if c["success_field"]:
            try:
                obj = json.loads(resp_text)
                cur = obj
                for k in c["success_field"].split("."):
                    cur = cur[k]
                want = c["success_value"].lower()
                got = str(cur).lower()
                biz_ok = (got == want)
            except Exception:
                biz_ok = False
        if biz_ok is not None:
            print(f"  → 业务校验（{c['success_field']}={c['success_value']}）: {biz_ok}")

        # 建议
        print("\n" + "-" * 56)
        if status == 404:
            print("⚠️ 状态码 404：接口不存在。")
            print("   下一步：")
            print("   1. 用 Chrome 打开投票详情页")
            print("   2. F12 → Network → 勾选 Fetch/XHR")
            print("   3. 手动点一次投票按钮")
            print("   4. 在列表中找到那条 POST 请求，复制 Request URL 到 submit_url")
            print("   5. 复制 Payload 到 data，Content-Type 到 content_type")
            print("   6. 再把 dry_run 改 True，验证一次")
        elif status == 403:
            print("⚠️ 状态码 403：权限拒绝或缺少 CSRF/Referer。")
            print("   下一步：检查 Cookie / CSRF token / Referer 是否正确。")
        elif status == 200 and biz_ok is not False:
            print("✓ 配置正确！status=200 且业务成功。")
            print("  → 现在可以把 dry_run 改 False，开始批量投票。")
        elif status == 200:
            print("⚠️ HTTP 200，但业务校验失败。")
            print("   下一步：检查 success_field / success_value 是否正确。")
        else:
            print(f"⚠️ 状态码 {status}，请根据上述响应内容判断问题。")
        print("-" * 56)
        return 0 if (status == 200 and biz_ok is not False) else 4

    # ---- 非 dry_run：走正常 mock/local/real 流程 ----

    if mode == "mock":
        # 本地 mock：每个 cookie 身份限 10 票，模拟"换浏览器续投"
        import threading, http.server, socketserver
        PER = int(c["per_profile"])
        _votes = {}

        class _H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                ln = int(self.headers.get("Content-Length", 0))
                self.rfile.read(ln)
                ck = self.headers.get("Cookie", "").strip()
                k = ck or "anon"
                _votes[k] = _votes.get(k, 0) + 1
                if _votes[k] > PER:
                    body = json.dumps({"success": False, "code": 403,
                                       "msg": "已达单身份上限，需换浏览器"}).encode()
                    self.send_response(403)
                else:
                    body = json.dumps({"success": True, "code": 0,
                                       "msg": "voted"}).encode()
                    self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        class _Srv(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
        srv = _Srv(("127.0.0.1", 8899), _H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        time.sleep(0.3)
        log.info("[mock] 本地投票服务已起在 127.0.0.1:8899")

        c["vote_url"] = "http://127.0.0.1:8899/vote.php?id=19"
        c["submit_url"] = "http://127.0.0.1:8899/ajax/vote"

    action = ActionScript(
        vote_url=c["vote_url"], submit_url=c["submit_url"],
        method=c["method"], content_type=c["content_type"],
        data=c["data"], success_field=c["success_field"],
        success_value=c["success_value"],
        choice_values=c.get("choice_values") or ["1"],
    )
    cfg = VoteConfig(
        vote_url=action.vote_url, submit_url=action.submit_url,
        method=action.method, data=action.data,
        content_type=action.content_type,
        success_field=action.success_field,
        success_value=action.success_value,
        total_votes=int(c["votes"]), per_profile=int(c["per_profile"]),
        between_vote_delay=float(c["between_vote_delay"]),
        between_profile_delay=float(c["between_profile_delay"]),
        timeout=float(c["timeout"]),
        driver=str(c["driver"]), chrome_path=str(c.get("chrome", "")),
        headless=bool(c.get("headless", False)),
        out=str(c.get("out", "vote1000_result.json")),
        stop_on_fail=bool(c.get("stop_on_fail", False)),
        keep_profiles=bool(c.get("keep_profiles", False)),
        proxy=str(c.get("proxy", "")),
        proxy_list=list(c.get("proxy_list") or []),
        flclash_api=str(c.get("flclash_api", "")),
        flclash_proxy_group=str(c.get("flclash_proxy_group", "GLOBAL")),
        flclash_switch_on_profile=bool(c.get("flclash_switch_on_profile", False)),
        http_warmup=bool(c.get("http_warmup", False)),
    )

    if cfg.proxy_list:
        print(f"[代理] IP 轮换：已加载 {len(cfg.proxy_list)} 个代理，每 profile 自动切换")
    elif cfg.proxy:
        print(f"[代理] 使用代理：{cfg.proxy}")

    # FlClash/草莓云 自动节点轮换（Spyder 模式）
    flclash = None
    if cfg.flclash_api:
        flclash = FlClashController(cfg.flclash_api, cfg.flclash_proxy_group)
        if flclash.available:
            print(f"[FlClash] API 已连接，代理组={cfg.flclash_proxy_group}，可用节点={len(flclash._node_list)}")
            if cfg.flclash_switch_on_profile:
                print(f"[FlClash] 每个 profile 自动切换一次节点")
        else:
            print(f"[FlClash] API 连接失败（{cfg.flclash_api} 无响应），将不切换节点")
            print(f"  如需自动换 IP：在草莓云/FlClash 设置中开启「外部控制 / External Controller」并设为 127.0.0.1:9090，重启草莓云后再运行；")
            print(f"  或：将草莓云设为「自动选择/负载均衡」模式，脚本仍走 127.0.0.1:7890 由草莓云内部轮换。")
            flclash = None

    workdir = str(c.get("workdir", ".vote1000_work"))
    orch = VoteOrchestrator(cfg, workdir, action)
    drv = cfg.driver
    print(f"[驱动] {drv}"
          + ("（纯 HTTP，不会启动任何浏览器）" if drv == "http" else "（会启动真实浏览器窗口）"))
    if flclash and cfg.flclash_switch_on_profile:
        orch._session_factory = lambda i: _make_session_with_flclash(
            i, cfg, action, flclash, orch.workdir, drv)
    else:
        orch._session_factory = lambda i: _build_session(
            i, cfg, action, workdir, drv)

    t0 = time.time()
    orch.run()
    elapsed = time.time() - t0
    s = orch.summary()
    orch.write_out(cfg.out)

    print("\n" + "=" * 56)
    print(f"完成：投 {s['total_voted']}/{cfg.total_votes} 票  成功 {s['success']}  "
          f"失败 {s['failed']}  业务失败 {s['biz_fail']}  身份数 {s['profiles_used']}")
    print(f"耗时 {elapsed:.1f}s，结果写入 {cfg.out}")
    if mode == "mock":
        print(f"（mock 模式，未碰真实站点）")
        try:
            srv.shutdown()
        except Exception:
            pass
    print("=" * 56)
    return 0 if (s["total_voted"] == cfg.total_votes and s["failed"] == 0) else 4


# ============================================================
# 统一入口（命令行 / Spyder 自适应）
# ============================================================
def _detect_interactive_env() -> bool:
    """是否在 Spyder / Jupyter / IPython 中运行（按 F5 打开文件时）。"""
    if "IPython" in sys.modules or "_IPython" in globals():
        return True
    if "spyder" in sys.modules:
        return True
    return False


def _auto_entry() -> int:
    """
    统一入口：
      - 在 Spyder/Jupyter 里（按 F5）→ 走 _run_in_spyder()（改 SPYDR_CONFIG 即可）
      - 在命令行 → 走 main()（带 argparse）
    """
    if _detect_interactive_env():
        return _run_in_spyder()
    return main()


if __name__ == "__main__":
    sys.exit(_auto_entry())
