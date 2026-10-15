# -*- coding: utf-8 -*-
"""启动或复用隔离的 Chrome CDP 会话，保留 BOSS 登录态。"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

from cdp_utils import build_search_url
from config import ProfileError, load_profile


def _find_chrome():
    """按常见位置自动查找 chrome.exe，兼容不同机器/用户名。"""
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return candidates[0]


# 自动探测：不写死用户名，换机器也能跑
CHROME = _find_chrome()
USER_DATA = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser(r"~\AppData\Local")),
    "Google", "Chrome", "UserData-CDP",
)
PORT = 9223
CDP_MARKER = "UserData-CDP"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="启动或复用 BOSS 自动投递所需的 Chrome CDP")
    parser.add_argument(
        "--restart",
        action="store_true",
        help="仅在 9223 不可用且 CDP Chrome 残留时，重启该隔离实例；不会动普通 Chrome",
    )
    return parser.parse_args(argv)


def port_open(port, timeout=2):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(("127.0.0.1", port))
        return True
    except Exception:
        return False
    finally:
        sock.close()


def build_chrome_command(chrome=CHROME, user_data=USER_DATA, port=PORT, start_url=None):
    cmd = [
        chrome,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={user_data}",
        "--profile-directory=Default",
        "--no-first-run",
        "--no-default-browser-check",
        "--start-maximized",
        # v22.2.9: 强制直连，忽略系统代理。
        # 原因：本机 FlClash 系统代理（127.0.0.1:7890）开着时，Chrome 会走代理节点出口，
        # BOSS 直聘看到的是代理 IP —— 这是风控的高权重特征（0911 实测：关代理后投 100 个零风控）。
        # 加此参数后无需每次手动关 FlClash，隔离实例始终直连。
        "--no-proxy-server",
    ]
    if start_url:
        cmd.append(start_url)
    return cmd


def parse_pid_output(output):
    pids = []
    for line in (output or "").splitlines():
        value = line.strip()
        if value.isdigit():
            pids.append(int(value))
    return pids


def find_cdp_processes(run=subprocess.run):
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
        f"Where-Object {{ $_.CommandLine -like '*{CDP_MARKER}*' }} | "
        "Select-Object -ExpandProperty ProcessId"
    )
    try:
        result = run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=20,
        )
    except Exception:
        return []
    return parse_pid_output(result.stdout)


def stop_processes(pids, run=subprocess.run):
    commands = [
        f"Stop-Process -Id {int(pid)} -Force -ErrorAction SilentlyContinue"
        for pid in pids
    ]
    if not commands:
        return
    run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", "; ".join(commands)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=20,
    )


def wait_for_port(port, attempts=30, interval=1.0):
    for index in range(attempts):
        if port_open(port):
            return index * interval
        time.sleep(interval)
    return None


def verify_cdp(port):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(f"http://127.0.0.1:{port}/json/version", timeout=5) as resp:
        version = json.loads(resp.read().decode())
    with opener.open(f"http://127.0.0.1:{port}/json", timeout=5) as resp:
        pages = json.loads(resp.read().decode())
    return version, pages


def main(argv=None):
    args = parse_args(argv)

    if port_open(PORT):
        print(f"[OK] CDP 已在 127.0.0.1:{PORT} 运行，直接复用；未结束任何 Chrome。", flush=True)
        return 0

    pids = find_cdp_processes()
    if pids:
        if not args.restart:
            joined = ", ".join(str(pid) for pid in pids)
            print(
                f"[FAIL] 检测到 CDP Chrome 残留进程({joined})，但 {PORT} 未开放。\n"
                "       先手动关闭该 CDP 窗口；确实需要自动重启时使用 --restart。",
                flush=True,
            )
            return 1
        print(f"[1/4] 仅重启 CDP Chrome 实例: {', '.join(str(pid) for pid in pids)}", flush=True)
        stop_processes(pids)
        time.sleep(3)

    # v23: 起始页面用 profile 里的第一个关键词 + 城市，不再写死行业词。
    # profile 缺失时不阻断启动（用户可能只是先开个 Chrome 去登录），
    # 退回 BOSS 首页并在日志里提示。
    try:
        prof = load_profile()
        start_url = build_search_url(prof['keywords'][0], prof['city_code'])
    except ProfileError as exc:
        print(f"[WARN] {exc}", flush=True)
        start_url = "https://www.zhipin.com/"
        print("       已退回 BOSS 首页启动；投递前请先补好 profile.json。", flush=True)
    print(f"[2/4] 启动隔离 Chrome (CDP port {PORT})...", flush=True)
    proc = subprocess.Popen(
        build_chrome_command(start_url=start_url),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"      Chrome PID: {proc.pid}", flush=True)

    print("[3/4] 等待端口开放...", flush=True)
    elapsed = wait_for_port(PORT)
    if elapsed is None:
        print("[FAIL] 端口未开放", flush=True)
        return 1
    print(f"      端口 {PORT} 已开放 ({elapsed:.0f}s)", flush=True)

    print("[4/4] 验证 CDP 接口...", flush=True)
    try:
        version, pages = verify_cdp(PORT)
        print(f"      Browser: {version.get('Browser')}", flush=True)
        print(f"      页面数: {len(pages)}", flush=True)
    except Exception as exc:
        print(f"      接口异常: {exc}", flush=True)
        return 1

    print("[OK] CDP 就绪，可以运行投递脚本。", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
