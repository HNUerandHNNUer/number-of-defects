#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
import json
import logging
import os
import random
import re
import shutil
import string
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
__BUILD__ = "2026-10-17 http-driver v3 (10票换IP)"

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

    # ============================================================
    # IP 轮换：每 POST N 次更换一次出口 IP（真实 IP 打 10 票 → 换 IP → 再打）
    # 思想来源（GitHub 常见三类换 IP 工具）：
    #   1) tor          —— Tor control 端口 SIGNAL NEWNYM 换出口节点
    #                      （GitHub: torproject/stem、github.com/topics/tor-ip-changer）
    #   2) adsl         —— Windows rasdial 宽带拨号断开重连，动态 IP 重播换 IP
    #                      （GitHub: 各类 adsl-redial / pppoe-rotate 脚本）
    #   3) proxy_list   —— 代理池逐个轮换
    #                      （GitHub: constverum/ProxyBroker 等代理池项目）
    #   4) flclash      —— FlClash/草莓云 external-controller 切换节点（本文件已有）
    # ============================================================
    ip_rotate_every: int = 10     # 每 POST 多少次换一次 IP（0=关闭；默认 10）
    ip_rotate_method: str = "auto"  # auto / tor / adsl / flclash / proxy_list / none
    tor_control_host: str = "127.0.0.1"
    tor_control_port: int = 9051
    tor_control_password: str = ""  # torrc 里 HashedControlPassword 对应的明文密码
    tor_socks: str = "socks5h://127.0.0.1:9050"  # Tor 本地 SOCKS 出口（tor 后端时使用）
    adsl_entry: str = ""          # 拨号连接名，如 "宽带连接"（ADSL 后端时使用）
    adsl_user: str = ""
    adsl_pass: str = ""
    ip_check_timeout: float = 6.0  # 探测出口 IP 的超时（秒）

    # ============================================================
    # VoteRobot 思想（GitHub: debugtalk/VoteRobot）
    # 目标网站通常按请求体中的身份标识（openid/opid）查重——"每用户每天 N 票"，
    # 但无法向微信等平台校验该标识的有效性。每次投票为身份字段生成全新随机值，
    # 对网站而言就是新用户，直接绕开按用户的限额（这比换 IP 更关键）。
    # ============================================================
    identity_fields: List[str] = field(default_factory=lambda: ["openid"])
    random_ua_per_vote: bool = True      # VoteRobot README 建议：每次投票换 UA，动态模拟设备
    rotate_on_quota_fail: bool = True    # 出现"次数已用完"类失败时立即提前换 IP（不硬撑到 N 票）


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
# 二.5、身份字段随机化（VoteRobot 思想）
# 参考 GitHub: debugtalk/VoteRobot —— 微信投票"刷票"案例分析
#   漏洞原理：投票网站按请求里的身份标识（OpenID/opid）查重
#   （每用户每天 N 票），但无法向微信等平台校验该标识的有效性；
#   因此每次投票生成一个全新随机身份标识，就等于换了一个"新用户"。
#   VoteRobot 原版做法：opid = getRandomString(22)，其余参数保持不变。
# ============================================================
def _rand_ident_like(orig: str) -> str:
    """按原值的格式生成随机身份标识（VoteRobot getRandomString 的同款思路）。"""
    n = len(orig)
    if n == 0:
        return orig
    if re.fullmatch(r"[0-9a-fA-F]{16,}", orig):
        # 十六进制串（token/hash 类）：随机等长 hex
        return os.urandom(max(1, n // 2)).hex()[:n]
    if orig.startswith("op") and re.fullmatch(r"[0-9A-Za-z]+", orig):
        # 微信 openid 风格：op 前缀 + 随机字母数字（VoteRobot 同款）
        return "op" + "".join(random.choice(string.ascii_letters + string.digits)
                             for _ in range(n - 2))
    if re.fullmatch(r"\d{6,}", orig):
        # 纯数字 ID：等长随机数字
        return str(random.randint(10 ** (n - 1), 10 ** n - 1))
    # 兜底：等长随机字母数字
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(n))


def _new_identity_value(field_name: str) -> str:
    """为空的身份字段生成全新随机值。

    - openid/opid 类：微信风格 "op"+22 位随机字母数字（VoteRobot 同款）
    - 其他字段：22 位随机字母数字
    """
    body = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(22))
    return ("op" + body) if ("openid" in field_name.lower()
                             or "opid" in field_name.lower()) else body


def _ensure_local_no_proxy() -> None:
    """确保 127.0.0.1/localhost 不走系统代理。

    有些用户机器配置了系统代理（或运行在带透明代理的环境里），
    不处理的话连本地 mock 服务都会被代理截走，导致 mock 模式失效、
    且非 JSON 响应会被误判为成功。这里只往 no_proxy 里补充本地地址，
    不影响其他主机走代理的行为。
    """
    for key in ("no_proxy", "NO_PROXY"):
        cur = os.environ.get(key, "")
        items = [x.strip() for x in cur.split(",") if x.strip()]
        for host in ("127.0.0.1", "localhost", "::1"):
            if host not in items:
                items.append(host)
        os.environ[key] = ",".join(items)


def randomize_identity_fields(body: str, fields: List[str]) -> str:
    """为请求体中的身份字段（openid/opid/token 等）生成全新随机值。

    同时兼容 `field=value`（表单）与 `"field":"value"`（JSON）两种写法。
    字段不在 fields 列表中的值保持原样（与 VoteRobot 一致：
    只有身份标识需要换，业务参数不动）。
    字段值为空（如 `openid=`）时也会填充随机值——空 openid 会让网站
    退化为按 IP 查重，填上随机 openid 后每票都是新用户，与 IP 无关。
    """
    if not fields:
        return body
    for f in fields:
        if not f:
            continue
        pattern = re.compile(r"(%s\s*[:=]\s*[\"']?)([^&\"'\s,}]*)" % re.escape(f))
        def _rep(m, _f=f):
            orig = m.group(2)
            if not orig:
                # 空值 → 生成全新随机身份（VoteRobot getRandomString 同款）
                return m.group(1) + _new_identity_value(_f)
            return m.group(1) + _rand_ident_like(orig)
        body = pattern.sub(_rep, body)
    return body


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


# ============================================================
# 三.7、IP 轮换器（每 POST N 次换一次出口 IP）
#
# 设计思想（GitHub 上三类经典换 IP 工具）：
#   1) Tor NEWNYM   —— torproject/stem 的 controller.signal(Signal.NEWNYM)
#                      向 Tor control 端口发 SIGNAL NEWNYM，强制建立新电路、
#                      换一个出口节点（新 IP）。这里用纯标准库 socket 实现
#                      等价的 control protocol，无需安装 stem。
#   2) ADSL 重拨     —— rasdial "宽带连接" /DISCONNECT 后重新拨号，
#                      运营商动态分配新 IP（GitHub adsl-redial 类脚本同款思路）。
#   3) 代理池轮换   —— constverum/ProxyBroker 类项目：维护一组代理，
#                      切换时取下一个，当前连接全部重建。
# 换 IP 之后必须让"当前会话"重建网络连接才生效：
#   - HTTP 驱动：重建 requests.Session / urllib Opener（旧连接仍走旧电路）
#   - CDP 驱动 ：关闭浏览器进程（保留 profile/cookie）后用新代理重启
#   - Playwright：关闭 context 后用相同 user-data-dir 重开
# ============================================================
IP_ECHO_APIS = [
    # (url, 解析方式)  —— 国内外混合，哪个通用哪个
    ("https://api.ipify.org", "plain"),
    ("https://ifconfig.me/ip", "plain"),
    ("https://myip.ipip.net", "regex"),            # 国内可用：返回 "当前 IP：x.x.x.x ..."
    ("http://members.3322.org/dyndns/getip", "plain"),  # 国内可用
    ("https://www.taobao.com/help/getip.php", "regex"),  # 国内可用
]

_IP_RE = re.compile(r"(\d{1,3}\.){3}\d{1,3}")


def _valid_ip(s: str) -> bool:
    if not s:
        return False
    parts = s.split(".")
    return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def get_exit_ip(proxy: str = "", timeout: float = 6.0) -> str:
    """探测当前出口 IP（走同一代理，才能反映轮换是否生效）。失败返回 ""。"""
    proxies = {"http": proxy, "https": proxy} if proxy else None
    for url, mode in IP_ECHO_APIS:
        txt = ""
        try:
            try:
                import requests as _rq
                r = _rq.get(url, proxies=proxies, timeout=timeout)
                txt = r.text or ""
            except ImportError:
                opener = HttpVoteSession._build_opener(proxy) if proxy \
                    else urllib.request.build_opener()
                req = urllib.request.Request(url, headers={"User-Agent": "vote1000/1.0"})
                with opener.open(req, timeout=timeout) as resp:
                    txt = resp.read().decode("utf-8", errors="replace")
            if mode == "regex":
                m = _IP_RE.search(txt)
                ip = m.group(0) if m else ""
            else:
                ip = txt.strip().splitlines()[0].strip() if txt.strip() else ""
            if _valid_ip(ip):
                return ip
        except Exception:
            continue
    return ""


class TorNewNymController:
    """通过 Tor control 端口发送 SIGNAL NEWNYM 更换出口 IP。

    对应 GitHub 项目 torproject/stem 的用法：
        from stem import Signal
        from stem.control import Controller
        with Controller.from_port(port=9051) as c:
            c.authenticate(password="...")
            c.signal(Signal.NEWNYM)
    这里用纯标准库 socket 实现等价逻辑（无需安装 stem）。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9051, password: str = ""):
        self.host = host
        self.port = port
        self.password = password
        self._last_newnym = 0.0

    def _cmd(self, cmd: str) -> str:
        """发一条 control protocol 命令（每条一个短连接），返回响应文本。"""
        try:
            with socket.create_connection((self.host, self.port), timeout=5) as s:
                s.sendall((cmd + "\r\n").encode("utf-8"))
                s.settimeout(3.0)
                chunks = b""
                try:
                    while True:
                        b = s.recv(4096)
                        if not b:
                            break
                        chunks += b
                        # 读到一条完整的状态行（3 位状态码 + 文本 + CRLF）即可返回
                        if b"\r\n" in chunks:
                            first = chunks.split(b"\r\n", 1)[0].decode("utf-8", "replace")
                            if len(first) >= 3 and first[:3].isdigit():
                                break
                except socket.timeout:
                    pass
                return chunks.decode("utf-8", errors="replace").strip()
        except Exception as e:
            log.debug("Tor control 命令失败 %s: %s", cmd, e)
            return ""

    @property
    def available(self) -> bool:
        """control 端口能握手即视为可用。"""
        r = self._cmd("PROTOCOLINFO 1")
        return r.startswith("250")

    def newnym(self, cooldown: float = 10.0) -> bool:
        """发送 SIGNAL NEWNYM。Tor 默认对 NEWNYM 限速（约 10s 一次），
        成功后等待 cooldown 秒让新电路建好。返回是否成功。"""
        auth = f'AUTHENTICATE "{self.password}"' if self.password else 'AUTHENTICATE ""'
        r1 = self._cmd(auth)
        if not r1.startswith("250"):
            log.debug("Tor AUTHENTICATE 失败: %s", r1[:80])
            return False
        r2 = self._cmd("SIGNAL NEWNYM")
        if not r2.startswith("250"):
            # 552 = 限速（太频繁），其他为错误
            log.debug("Tor SIGNAL NEWNYM 响应: %s", r2[:80])
            return False
        self._last_newnym = time.time()
        # 等新电路建立（NEWNYM 只保证"之后新建的连接"用新电路）
        wait = min(cooldown, 10.0)
        log.info("[Tor] NEWNYM 已发送，等待 %.0fs 让新电路建立...", wait)
        time.sleep(wait)
        return True


class ADSLRedialer:
    """Windows 宽带拨号（rasdial）断开重连换 IP。

    对应 GitHub adsl-redial / pppoe-rotate 类脚本的标准做法：
        rasdial "宽带连接" /DISCONNECT
        rasdial "宽带连接" 用户名 密码
    重拨后运营商会动态分配一个新 IP（仅 ADSL/PPPoE 动态 IP 有效）。
    """

    def __init__(self, entry: str = "宽带连接", user: str = "", password: str = ""):
        self.entry = entry
        self.user = user
        self.password = password

    @property
    def available(self) -> bool:
        return os.name == "nt" and bool(self.entry)

    def _run(self, args: List[str]) -> str:
        try:
            out = subprocess.run(
                args, capture_output=True, timeout=30,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            raw = (out.stdout or b"") + (out.stderr or b"")
            if isinstance(raw, bytes):
                # 中文 Windows 的 rasdial 输出是 GBK
                for enc in ("gbk", "gb18030", "utf-8"):
                    try:
                        return raw.decode(enc, errors="replace")
                    except Exception:
                        continue
                return raw.decode("latin-1", errors="replace")
            return raw
        except Exception as e:
            log.debug("rasdial 执行失败: %s", e)
            return ""

    def redial(self) -> bool:
        log.info("[ADSL] 正在断开拨号连接 %r ...", self.entry)
        self._run(["rasdial", self.entry, "/DISCONNECT"])
        time.sleep(1.5)
        log.info("[ADSL] 正在重新拨号 %r ...", self.entry)
        out = self._run(["rasdial", self.entry, self.user, self.password])
        ok = ("已连接" in out) or ("Command completed" in out) or (out.strip() == "")
        if not ok:
            log.warning("[ADSL] 重拨可能失败: %s", out.strip()[:120])
        else:
            log.info("[ADSL] 重拨完成")
        return ok


class IPRotator:
    """IP 轮换器：每 N 次 POST 换一次出口 IP。

    后端优先级（method=auto 时）：proxy_list > flclash > tor > adsl
    （tor/adsl 只有在流量走向匹配时才会被 auto 选中，详见 _available_backends）
    也可用 ip_rotate_method 显式指定。切换逻辑：
      - tor         → SIGNAL NEWNYM 换电路（流量须走 Tor SOCKS 才生效）
      - flclash     → FlClash/草莓云切下一个节点（流量须走 127.0.0.1:7890）
      - proxy_list  → 代理池取下一个代理（同步写回 cfg.proxy）
      - adsl        → rasdial 断开重拨（流量须直连才生效）
    """

    def __init__(self, cfg: VoteConfig):
        self.cfg = cfg
        self.enabled = bool(cfg.ip_rotate_every)
        self.method = (cfg.ip_rotate_method or "auto").lower()
        self.rotate_count = 0
        self.ip_tag = ""            # 最近一次探测到的出口 IP
        self.last_ok = False        # 最近一次 rotate() 是否真正执行了切换
        self._warned_no_backend = False
        self.current_proxy = cfg.proxy or ""
        self.tor = TorNewNymController(
            cfg.tor_control_host, cfg.tor_control_port, cfg.tor_control_password)
        self.adsl = ADSLRedialer(cfg.adsl_entry, cfg.adsl_user, cfg.adsl_pass) \
            if cfg.adsl_entry else None
        self.flclash = FlClashController(cfg.flclash_api, cfg.flclash_proxy_group) \
            if cfg.flclash_api else None
        # 代理池模式：从第一个代理开始
        if cfg.proxy_list:
            self.current_proxy = cfg.proxy_list[0]
            self._proxy_idx = 0
        else:
            self._proxy_idx = -1
        # 显式选 tor 但流量没走 Tor 时给出提醒（NEWNYM 不会改变实际出口 IP）
        if self.method == "tor" and not self._traffic_via_tor():
            log.warning("[Tor] 注意：当前流量未经过 Tor SOCKS 出口，NEWNYM 可能不改变真实 IP。"
                        "请把 --proxy 设为 socks5h://127.0.0.1:9050（或 Tor Browser 的 9150）。")

    def _traffic_via_tor(self) -> bool:
        """当前 cfg.proxy 是否指向 Tor 的 SOCKS 出口。"""
        p = (self.cfg.proxy or "").lower()
        if not p:
            return False
        return ("9050" in p) or ("9150" in p) or ("tor" in p)

    # ---- 后端探测 ----
    def _available_backends(self) -> List[str]:
        """按 auto 优先级返回可用后端。

        注意：后端必须和"流量实际走向"匹配才有效——
          proxy_list：流量走代理池，切代理即换 IP          → 始终可用
          flclash   ：流量走 127.0.0.1:7890，切节点即换 IP → API 通即可用
          tor       ：流量必须走 Tor SOCKS，NEWNYM 才换 IP  → 代理指向 Tor 时才入选
          adsl      ：流量必须直连，重拨才换 IP            → 未配代理时才入选
        """
        out: List[str] = []
        if self.cfg.proxy_list:
            out.append("proxy_list")
        if self.flclash is not None and self.flclash.available:
            out.append("flclash")
        if self.tor.available and self._traffic_via_tor():
            out.append("tor")
        if self.adsl is not None and self.adsl.available and not (self.cfg.proxy or ""):
            out.append("adsl")
        return out

    def backend(self) -> str:
        """实际生效的后端名；没有可用后端返回 ""。"""
        if not self.enabled:
            return ""
        avail = self._available_backends()
        if self.method in ("tor", "adsl", "flclash", "proxy_list"):
            return self.method if self.method in avail else ""
        # auto
        for b in avail:   # 探测顺序即优先级
            return b
        return ""

    # ---- 出口 IP 探测 ----
    def probe_ip(self) -> str:
        ip = get_exit_ip(self.current_proxy, timeout=self.cfg.ip_check_timeout)
        if ip:
            self.ip_tag = ip
        return ip

    # ---- 换一次 IP ----
    def rotate(self) -> str:
        """执行一次换 IP，返回新 IP（探测失败返回 ""）。"""
        b = self.backend()
        if not b:
            if not self._warned_no_backend:
                self._warned_no_backend = True
                log.warning("[IP轮换] 当前没有可用的换 IP 后端"
                            "（tor 需流量走 Tor SOCKS；flclash 需开启 external-controller；"
                            "或配置代理池/ADSL 拨号），本次运行将不换 IP。")
            self.last_ok = False
            return ""
        old_ip = self.ip_tag
        if b == "tor":
            # NEWNYM 只影响之后新建的连接；HTTP 驱动靠重建 Session 拿新电路
            self.tor.newnym()
        elif b == "flclash":
            self.flclash.switch_next()
        elif b == "proxy_list":
            self._proxy_idx = (self._proxy_idx + 1) % len(self.cfg.proxy_list)
            self.current_proxy = self.cfg.proxy_list[self._proxy_idx]
            # 同步回 cfg，让会话层（Chrome 启动参数 / requests 代理）读到新代理
            self.cfg.proxy = self.current_proxy
        elif b == "adsl":
            self.adsl.redial()
        self.rotate_count += 1
        self.last_ok = True
        new_ip = self.probe_ip()
        log.info("[IP轮换#%d] 后端=%s  IP: %s -> %s", self.rotate_count, b,
                 old_ip or "未知", new_ip or "探测失败")
        return new_ip


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
                  headless: bool = False, proxy: str = "",
                  fresh: bool = True) -> subprocess.Popen:
    """启动一个隔离的 Chrome/Edge 实例（独立 profile + CDP 端口）。

    fresh=False 时保留原 profile 目录（换 IP 后重启浏览器、不清 cookie）。
    """
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

    # 清理锁文件和旧 profile 目录（fresh=False 表示换 IP 重启，保留 cookie）
    if fresh and os.path.isdir(user_data_dir):
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
    ip: str = ""             # 本次投票时的出口 IP（IP 轮换开启时由编排器回填）


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
    def _launch_and_connect(self, fresh: bool = True) -> None:
        """启动 Chrome（fresh=False 时保留 profile/cookie）并连上 CDP。"""
        chrome = self.cfg.chrome_path or find_chrome()
        if not chrome:
            raise CDPError("未找到 Chrome/Edge。请用 --chrome 指定可执行路径，"
                           "或安装 Chrome/Edge 后重试。")
        self._chrome_path = chrome
        self._proc = launch_chrome(
            chrome, self.user_data_dir, self.cdp_port, self.cfg.headless,
            proxy=self.cfg.proxy or "",  # 传递代理给 Chrome（换 IP 后这里就是新代理）
            fresh=fresh,
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

    def start(self) -> None:
        self._launch_and_connect(fresh=True)

    def rotate_ip(self) -> None:
        """换 IP 后调用：重启浏览器让新代理生效（保留 profile，cookie 不丢）。

        调用方（编排器）已完成换 IP（cfg.proxy 已更新），这里只需要：
          1. 关闭当前 CDP 连接与浏览器进程
          2. 用同一 profile 重新启动（launch_chrome 会读新的 cfg.proxy）
          3. 重新注入指纹并打开投票页，恢复投票上下文
        """
        log.info("[IP轮换] profile#%d 重启浏览器以使新 IP 生效（保留 cookie）", self.index)
        if self._ws:
            try:
                self._ws.send_command("Browser.close")
            except Exception:
                pass
            try:
                self._ws.close()
            except Exception:
                pass
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
        self._launch_and_connect(fresh=False)
        self._apply_fingerprint()
        self._navigate(self.action.vote_url, wait=2.0)

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
        # VoteRobot 思想：填充模板后，为身份字段（openid 等）生成全新随机值
        body = randomize_identity_fields(fill_template(self.action.data, ctx),
                                         cfg.identity_fields)
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
        # IP 轮换：每 N 次 POST 换一次出口 IP
        self.rotator: Optional[IPRotator] = None
        self._votes_since_rotate = 0
        # 业务失败（如"次数已用完"）触发提前换 IP 的次数上限（防止无限空转）
        self._forced_rotations = 0

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
        # ---- 初始化 IP 轮换器（每 N 票换一次 IP）----
        if cfg.ip_rotate_every:
            self.rotator = IPRotator(cfg)
            backend = self.rotator.backend()
            if backend:
                ip = self.rotator.probe_ip()
                log.info("[IP轮换] 已启用：每 POST %d 票换一次 IP（后端=%s，当前出口 IP=%s）",
                         cfg.ip_rotate_every, backend, ip or "未知")
            else:
                log.warning("[IP轮换] 已启用但未找到可用后端"
                            "（tor 需 Tor Browser/系统 Tor；flclash 需开启 external-controller；"
                            "或配置 --proxy-list / --adsl-entry），本次运行将不换 IP。")
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
                    if self.rotator is not None:
                        res.ip = self.rotator.ip_tag
                    self.all_results.append(res)
                    if res.ok:
                        self.success += 1
                    else:
                        self.failed += 1
                        if res.biz_ok is False:
                            self.biz_fail += 1
                    self._progress(res)
                    # VoteRobot 配套策略：业务失败（如"今日次数已用完"）说明当前
                    # 出口 IP 的额度已耗尽，立即提前换 IP，不等满 N 票硬撑。
                    if (res.biz_ok is False and cfg.rotate_on_quota_fail
                            and self.rotator is not None):
                        if self._forced_rotations < 50:
                            self._forced_rotations += 1
                            log.info("[IP轮换] 业务失败（%s），立即提前换 IP（第 %d 次）",
                                     (res.reason or "未知原因")[:40],
                                     self._forced_rotations)
                            self._votes_since_rotate = 0
                            self._rotate_ip(sess)
                        elif self._forced_rotations == 50:
                            self._forced_rotations += 1
                            log.warning("[IP轮换] 提前换 IP 已达 50 次，疑似后端无法产出新 IP"
                                        "（或站点风控升级），自动停止提前轮换，回归按票数轮换。")
                    # ---- 核心：每 N 次 POST 换一次 IP ----
                    if self.rotator is not None:
                        self._votes_since_rotate += 1
                        if self._votes_since_rotate >= cfg.ip_rotate_every:
                            self._votes_since_rotate = 0
                            self._rotate_ip(sess)
            except Exception as e:
                log.error("profile#%d 投票过程异常：%s", sess.index, e)
                self.failed += n_this - len(sess.results)
            finally:
                sess.stop()
            # profile 间隔
            if self.global_votes < cfg.total_votes:
                time.sleep(cfg.between_profile_delay)

    def _rotate_ip(self, sess) -> None:
        """执行一次换 IP，并让当前会话立刻使用新 IP。"""
        try:
            self.rotator.rotate()
        except Exception as e:
            log.warning("[IP轮换] 换 IP 失败：%s", e)
            return
        if not self.rotator.last_ok:
            return   # 没真正换成功，不折腾会话连接
        # 会话层重绑网络（HTTP 重建连接 / CDP 重启浏览器 / Playwright 重建 context）
        rebind = getattr(sess, "rotate_ip", None)
        if callable(rebind):
            try:
                rebind()
            except Exception as e:
                log.warning("[IP轮换] 会话重绑网络失败（%s），后续票可能仍走旧 IP", e)

    def _progress(self, res: VoteResult) -> None:
        total = self.cfg.total_votes
        pct = self.global_votes / total
        bar = "#" * int(20 * pct) + "-" * int(20 * (1 - pct))
        proxy_info = f" proxy={res.proxy}" if res.proxy else ""
        ip_info = f" ip={res.ip}" if res.ip else ""
        log.info("  [%s] %5d/%d  P%d  第%d票 status=%s ok=%s%s%s%s",
                 bar, self.global_votes, total,
                 res.profile_id, res.seq, res.status, res.ok,
                 proxy_info, ip_info,
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
                    "ok", "attempts", "elapsed_ms", "reason", "proxy", "ip"]
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
        # VoteRobot 思想：填充模板后，为身份字段（openid 等）生成全新随机值
        body = randomize_identity_fields(
            fill_template(self.action.data, cvars), self.cfg.identity_fields)
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

    def rotate_ip(self) -> None:
        """换 IP 后重建浏览器 context（旧 context 的连接仍走旧 IP）。"""
        log.info("[IP轮换] Playwright context 重建中...")
        self.stop()
        self.start()


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
        """提交用 POST 头。可选每次投票换 UA（VoteRobot README 建议：动态模拟设备）。"""
        ua = (pick_fp(self.cfg, "ua") if self.cfg.random_ua_per_vote
              else self._ua) or self._ua or "Mozilla/5.0"
        return {
            "Content-Type": self.action.content_type,
            "Cookie": self._cookie,
            "User-Agent": ua,
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

    def rotate_ip(self) -> None:
        """换 IP 后重建网络连接。

        requests.Session / urllib Opener 的连接池仍绑定旧代理、旧 Tor 电路，
        必须整体重建，后续 POST 才会走新 IP。UA/Cookie 等身份保持不变。
        """
        self._proxy = self.cfg.proxy or ""
        if self._use_requests:
            if self._session:
                try:
                    self._session.close()
                except Exception:
                    pass
            self._session = self._build_requests_session(self._proxy)
        else:
            self._opener = self._build_opener(self._proxy)
        log.info("[IP轮换] HTTP 会话已重建连接（proxy=%s）", self._proxy or "直连")

    @staticmethod
    def _build_opener(proxy: str = ""):
        _ensure_local_no_proxy()   # 本地地址（mock 等）永不走系统代理
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
        _ensure_local_no_proxy()   # 本地地址（mock 等）永不走系统代理
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
        # VoteRobot 思想：填充模板后，为身份字段（openid 等）生成全新随机值
        body = randomize_identity_fields(
            fill_template(self.action.data, cvars),
            self.cfg.identity_fields).encode("utf-8")
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
        description="自动轮换浏览器 profile 投票工具；并支持每 N 票自动更换出口 IP"
                    "（Tor NEWNYM / ADSL 重拨 / 代理池 / FlClash 节点，默认 10 票一换）",
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

    g3c = p.add_argument_group("IP 轮换（每 N 票换一次出口 IP）")
    g3c.add_argument("--ip-rotate-every", type=int, default=10,
                     help="每 POST 多少次换一次 IP（默认 10；0=关闭）")
    g3c.add_argument("--ip-rotate-method", default="auto",
                     choices=["auto", "tor", "adsl", "flclash", "proxy_list", "none"],
                     help="换 IP 后端：auto 自动选择 / tor(Tor NEWNYM) / "
                          "adsl(rasdial重拨) / flclash(切节点) / proxy_list(代理池)")
    g3c.add_argument("--tor-control-port", type=int, default=9051,
                     help="Tor control 端口（默认 9051）")
    g3c.add_argument("--tor-control-password", default="",
                     help="Tor control 认证密码（torrc 里 HashedControlPassword 对应明文）")
    g3c.add_argument("--tor-socks", default="socks5h://127.0.0.1:9050",
                     help="Tor 本地 SOCKS 出口；选 tor 后端且未指定 --proxy 时自动使用")
    g3c.add_argument("--adsl-entry", default="",
                     help="ADSL 拨号连接名（如 宽带连接），配置后启用 rasdial 重拨换 IP")
    g3c.add_argument("--adsl-user", default="", help="宽带账号")
    g3c.add_argument("--adsl-pass", default="", help="宽带密码")
    g3c.add_argument("--ip-check-timeout", type=float, default=6.0,
                     help="探测出口 IP 的超时（秒）")

    g4 = p.add_argument_group("身份随机化（VoteRobot 思想：每票换一个全新身份标识）")
    g4.add_argument("--identity-fields", default="openid",
                    help="请求体中要每次随机化的身份字段，逗号分隔（默认 openid）。"
                         "网站按该字段查重但无法校验其有效性；若仍失败可加 token 等再试")
    g4.add_argument("--no-random-ua-per-vote", action="store_true",
                    help="关闭每次投票随机 User-Agent（默认开启，VoteRobot 建议动态模拟设备）")
    g4.add_argument("--no-rotate-on-quota-fail", action="store_true",
                    help="关闭'业务失败时立即提前换 IP'（默认开启）")

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
        # IP 轮换（每 N 票换一次出口 IP）
        ip_rotate_every=args.ip_rotate_every,
        ip_rotate_method=args.ip_rotate_method,
        tor_control_port=args.tor_control_port,
        tor_control_password=args.tor_control_password,
        tor_socks=args.tor_socks,
        adsl_entry=args.adsl_entry,
        adsl_user=args.adsl_user,
        adsl_pass=args.adsl_pass,
        ip_check_timeout=args.ip_check_timeout,
        # 身份随机化（VoteRobot 思想）
        identity_fields=[s.strip() for s in (args.identity_fields or "").split(",")
                         if s.strip()],
        random_ua_per_vote=not args.no_random_ua_per_vote,
        rotate_on_quota_fail=not args.no_rotate_on_quota_fail,
    )
    # 显式选 tor 后端且未指定代理时，自动使用 Tor 本地 SOCKS 出口
    if cfg.ip_rotate_method == "tor" and not cfg.proxy:
        cfg.proxy = cfg.tor_socks
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
    if cfg.ip_rotate_every:
        log.info("IP 轮换：每 POST %d 票自动更换一次出口 IP（方法=%s，auto=自动选择后端）",
                 cfg.ip_rotate_every, cfg.ip_rotate_method)
        if cfg.flclash_switch_on_profile:
            log.info("  已启用按票数轮换，忽略 --flclash-switch-on-profile（避免重复切节点）")
    if cfg.identity_fields:
        log.info("身份随机化（VoteRobot 思想）：每次投票为字段 %s 生成全新随机值，"
                 "对网站而言就是新用户", cfg.identity_fields)

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

    if flclash and cfg.flclash_switch_on_profile and not cfg.ip_rotate_every:
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

    # ---- IP 轮换：每 POST N 票更换一次出口 IP ----
    #   核心思想：一个真实 IP 只打 10 票，然后换一个新 IP 再打 10 票。
    #   换 IP 后端（ip_rotate_method）：
    #     auto       自动挑选可用后端（proxy_list > flclash > tor > adsl）
    #     tor        Tor control 端口 SIGNAL NEWNYM 换出口电路
    #               （GitHub torproject/stem 同款思想；流量须走 Tor SOCKS：
    #                把 proxy 设为 socks5h://127.0.0.1:9050）
    #     adsl       Windows rasdial 宽带重拨，运营商分新 IP
    #               （GitHub adsl-redial 类脚本同款思想；流量须直连：proxy 留空）
    #     flclash    草莓云 external-controller 切下一个节点（流量走 127.0.0.1:7890）
    #     proxy_list 代理池逐个轮换（proxy_list 填代理文件路径）
    #   注意：ip_rotate_every > 0 时按票数轮换，自动忽略上面的 flclash_switch_on_profile。
    "ip_rotate_every": 10,
    "ip_rotate_method": "auto",
    "tor_control_port": 9051,
    "tor_control_password": "",
    "tor_socks": "socks5h://127.0.0.1:9050",
    "adsl_entry": "",
    "adsl_user": "",
    "adsl_pass": "",
    "ip_check_timeout": 6.0,

    # ---- 身份随机化（VoteRobot 思想，github.com/debugtalk/VoteRobot）----
    #   目标网站按 data 里的身份字段（openid）查重："每用户每天 10 票"，
    #   但无法向微信校验 openid 有效性 → 每次投票随机换一个 openid = 新用户。
    #   这往往比换 IP 更关键：IP 没变但身份换了，一样能继续投。
    #   若仍失败，把 "token" 也加进来试试。
    "identity_fields": ["openid"],
    "random_ua_per_vote": True,      # 每次投票换 UA（模拟不同设备）
    "rotate_on_quota_fail": True,    # 出现"次数已用完"类失败时立即提前换 IP
    "mock_port": 8899,               # mock 模式本地服务端口（占用时改这个）

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
    "votes": 2222,  # 先测试 20 票
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
        # 本地 mock：按请求体里的 openid 查重（每身份限 N 票），
        # 模拟目标网站"每用户每天 N 票、但无法校验 openid 有效性"的真实机制。
        # 打开身份随机化（identity_fields=["openid"]）时每票都是新用户 → 永远投得进；
        # 关闭后则和真实网站一样，同一 openid 投满 N 票后返回"次数已用完"。
        import threading, http.server, socketserver
        PER = int(c["per_profile"])
        _votes = {}
        class _H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                ln = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(ln).decode("utf-8", errors="replace") if ln else ""
                try:
                    # keep_blank_values=True：`openid=`（空值）也必须计入，
                    # 真实网站对空 openid 会退化为按 IP 查重
                    kv = urllib.parse.parse_qs(raw, keep_blank_values=True)
                except Exception:
                    kv = {}
                # 身份标识：openid/opid 优先，退化到 Cookie（模拟不同网站的查重维度）
                ident = (kv.get("openid") or kv.get("opid")
                         or [self.headers.get("Cookie", "").strip() or "anon"])[0]
                _votes[ident] = _votes.get(ident, 0) + 1
                if _votes[ident] > PER:
                    body = json.dumps({"success": False, "code": 403,
                                       "msg": "今日投票次数(10票)已用完，明天再来"}).encode()
                    self.send_response(403)
                else:
                    body = json.dumps({"success": True, "code": 1,
                                       "msg": "voted"}).encode()
                    self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        class _Srv(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
        mock_port = int(c.get("mock_port", 8899))
        try:
            srv = _Srv(("127.0.0.1", mock_port), _H)
        except OSError as e:
            print(f"[mock] 端口 {mock_port} 绑定失败：{e}")
            print(f"       可能有残留的 mock 服务占用该端口，改 SPYDER_CONFIG 的 mock_port 后重试。")
            return 5
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        time.sleep(0.3)
        log.info("[mock] 本地投票服务已起在 127.0.0.1:%d", mock_port)

        c["vote_url"] = f"http://127.0.0.1:{mock_port}/vote.php?id=19"
        c["submit_url"] = f"http://127.0.0.1:{mock_port}/ajax/vote"

    action = ActionScript(
        vote_url=c["vote_url"], submit_url=c["submit_url"],
        method=c["method"], content_type=c["content_type"],
        data=c["data"], success_field=c["success_field"],
        success_value=c["success_value"],
        choice_values=c.get("choice_values") or ["1"],
    )
    # 代理列表：支持文件路径（每行一个）或 Python 列表
    proxy_list = []
    _pl = c.get("proxy_list") or []
    if isinstance(_pl, str):
        if _pl and os.path.isfile(_pl):
            with open(_pl, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        proxy_list.append(line)
    elif isinstance(_pl, (list, tuple)):
        proxy_list = [str(x) for x in _pl]

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
        proxy_list=proxy_list,
        flclash_api=str(c.get("flclash_api", "")),
        flclash_proxy_group=str(c.get("flclash_proxy_group", "GLOBAL")),
        flclash_switch_on_profile=bool(c.get("flclash_switch_on_profile", False)),
        http_warmup=bool(c.get("http_warmup", False)),
        # IP 轮换（每 N 票换一次出口 IP）
        ip_rotate_every=int(c.get("ip_rotate_every", 10)),
        ip_rotate_method=str(c.get("ip_rotate_method", "auto")),
        tor_control_host="127.0.0.1",
        tor_control_port=int(c.get("tor_control_port", 9051)),
        tor_control_password=str(c.get("tor_control_password", "")),
        tor_socks=str(c.get("tor_socks", "socks5h://127.0.0.1:9050")),
        adsl_entry=str(c.get("adsl_entry", "")),
        adsl_user=str(c.get("adsl_user", "")),
        adsl_pass=str(c.get("adsl_pass", "")),
        ip_check_timeout=float(c.get("ip_check_timeout", 6.0)),
        # 身份随机化（VoteRobot 思想）
        identity_fields=(lambda x: [s.strip() for s in x.split(",") if s.strip()]
                         if isinstance(x, str) else list(x or []))(
            c.get("identity_fields", ["openid"])),
        random_ua_per_vote=bool(c.get("random_ua_per_vote", True)),
        rotate_on_quota_fail=bool(c.get("rotate_on_quota_fail", True)),
    )
    # 显式选 tor 后端且未指定代理时，自动使用 Tor 本地 SOCKS 出口
    if cfg.ip_rotate_method == "tor" and not cfg.proxy:
        cfg.proxy = cfg.tor_socks

    if cfg.proxy_list:
        print(f"[代理] IP 轮换：已加载 {len(cfg.proxy_list)} 个代理，按票数自动切换")
    elif cfg.proxy:
        print(f"[代理] 使用代理：{cfg.proxy}")
    if cfg.ip_rotate_every:
        print(f"[IP轮换] 每 POST {cfg.ip_rotate_every} 票自动更换一次出口 IP"
              f"（方法={cfg.ip_rotate_method}，auto=自动选择后端）")
    if cfg.identity_fields:
        print(f"[身份] VoteRobot 思想：每次投票为字段 {cfg.identity_fields} 生成全新随机值"
              f"（网站只查重、无法校验其有效性 → 等同于新用户）")

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
    if flclash and cfg.flclash_switch_on_profile and not cfg.ip_rotate_every:
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
            srv.server_close()   # 必须关 socket，否则 Windows 下同端口再绑定时请求仍会路由到旧服务
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
