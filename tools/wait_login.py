# -*- coding: utf-8 -*-
"""等待人工登录，并用【HttpOnly cookie 变化】作为登录判据；登录成功后优雅关闭浏览器保住 cookie。

=== 2026-09-17 修复的三件事 ===

【坑 1】登录判据不可靠（误判）
  旧判据读页面文本 —— "不含『登录/注册』即已登录"。页面停在 code_35 安全验证页
  (verify.html) 时文本自然不含「登录/注册」，被误判为【已登录】，投递白跑。
  → 现改为读 HttpOnly cookie（zp_at / wt2）：服务端签发新 token 必然改变其值，
    这是服务端级的硬判据，无法造假。

【坑 2】登录后 cookie 丢失（用户每次登录都白登）
  start_cdp_v2.py 用 subprocess.Popen 启动 Chrome → Chrome 是脚本子进程 →
  后台任务结束时 WorkBuddy 回收整个进程树 → Chrome 被【强杀】→ cookie 来不及写盘。
  用户现象："每次登录完浏览器就闪退"，且磁盘上 cookie 文件的 zp_at/wt2 一字未变。
  → 现改为：登录成功后 sleep 让 cookie 落盘，再主动发 Browser.close【优雅关闭】
    （Chrome 正常退出会 flush cookie），然后再由投递任务重新拉起。

【坑 3】探测本身加重风控
  曾用 fetch('/wapi/.../joblist.json') 每 4 秒探测一次 —— 等于高频注入 XHR，
  直接触发 code_37「您的环境存在异常」。
  → 现改为 Network.getCookies（CDP 本地读取，零网络请求），只在登录成功后
    才做【一次】接口验证。

退出码：0 = 已登录且接口健康；1 = 超时/未登录/风控未解除。
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import websocket

SKILL_DIR = r"C:\Users\17867\.workbuddy\skills\bosszhipin-cdp-auto-apply"
PORT = 9223
LOGIN_URL = "https://www.zhipin.com/web/user/?ka=header-login"
JOBS_URL = ("https://www.zhipin.com/web/geek/jobs"
            "?query=%E6%95%B0%E6%8D%AE%E5%BC%80%E5%8F%91&city=101010100")

DOM_JS = """(function(){
  var b = document.body;
  if (!b) return 'LOADING';
  var t = (b.innerText || '').replace(/\\s+/g, ' ');
  if (location.href.indexOf('/passport/') >= 0 || t.indexOf('安全验证') >= 0) return 'RISK_PAGE';
  if (t.indexOf('登录/注册') >= 0 || t.indexOf('登录 / 注册') >= 0 || t.indexOf('立即登录') >= 0) return 'NEED_LOGIN';
  return 'OTHER';
})()"""

# 登录成功后做【一次】接口验证（低频，仅一次，避免高频探测触发风控）
PROBE_JS = """(async function(){
  try {
    var u = '/wapi/zpgeek/search/joblist.json?scene=1&query=%E6%95%B0%E6%8D%AE%E5%BC%80%E5%8F%91&city=101010100&page=1&pageSize=30';
    var r = await fetch(u, {headers:{'accept':'application/json'}, credentials:'include'});
    var j = await r.json();
    if (j.code !== 0) return JSON.stringify({state:'RISK', code:j.code, msg:(j.message||'').slice(0,60)});
    var L = (j.zpData||{}).jobList || [];
    var withSal = 0;
    for (var i=0;i<L.length;i++){ if (L[i].salaryDesc) withSal++; }
    return JSON.stringify({state:'OK', total:L.length, withSal:withSal});
  } catch(e) { return JSON.stringify({state:'ERR', msg:String(e).slice(0,90)}); }
})()"""


def log(msg=""):
    print(msg, flush=True)


def start_chrome():
    starter = os.path.join(SKILL_DIR, "scripts", "start_cdp_v2.py")
    if not os.path.isfile(starter):
        log(f"[FATAL] 找不到启动器: {starter}")
        return False
    log("[1/5] 启动/复用 CDP Chrome ...")
    r = subprocess.run([sys.executable, starter], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    for line in (r.stdout or "").strip().splitlines():
        log("      " + line)
    if r.returncode != 0:
        log("[FATAL] 启动器返回非 0，Chrome 未就绪")
        return False
    return True


def pick_page():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    pages = json.loads(
        opener.open(f"http://127.0.0.1:{PORT}/json/list", timeout=5).read().decode())
    fallback = None
    for p in pages:
        if p.get("type") != "page":
            continue
        if "zhipin.com" in (p.get("url") or ""):
            return p
        if fallback is None:
            fallback = p
    return fallback


def connect(page):
    return websocket.create_connection(
        page["webSocketDebuggerUrl"], timeout=20,
        http_no_proxy=["127.0.0.1", "localhost", "::1"])


class Client:
    """极简 CDP 客户端，串行发号。"""

    def __init__(self, ws):
        self.ws = ws
        self.mid = 0
        self._net_on = False

    def call(self, method, params=None, timeout=25):
        self.mid += 1
        my = self.mid
        self.ws.send(json.dumps({"id": my, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = json.loads(self.ws.recv())
            if r.get("id") == my:
                return r
        return None

    def eval(self, expr, await_promise=False):
        p = {"expression": expr, "returnByValue": True}
        if await_promise:
            p["awaitPromise"] = True
        r = self.call("Runtime.evaluate", p)
        return ((r or {}).get("result", {}).get("result", {}) or {}).get("value")

    def ensure_network(self):
        if not self._net_on:
            self.call("Network.enable")
            self._net_on = True

    def auth_cookies(self):
        """读 HttpOnly 登录凭证 cookie —— 纯本地 CDP 读取，零网络请求。"""
        self.ensure_network()
        r = self.call("Network.getCookies", {"urls": ["https://www.zhipin.com"]})
        cookies = ((r or {}).get("result", {}) or {}).get("cookies", [])
        out = {}
        for c in cookies:
            n = c.get("name", "")
            if n in ("zp_at", "wt2", "__zp_stoken__"):
                out[n] = c.get("value", "")
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=1800, help="等待登录的最大秒数，默认 1800")
    ap.add_argument("--keep-open", action="store_true",
                    help="登录成功后不关闭浏览器（默认关闭以保存 cookie）")
    args = ap.parse_args()

    if not start_chrome():
        return 1

    log("[2/5] 连接 CDP，读取登录凭证 cookie 作为基线 ...")
    page = pick_page()
    if not page:
        log("[FATAL] 没有可用的 CDP 页面")
        return 1
    cli = Client(connect(page))

    # 确保页面在 zhipin 域
    url = cli.eval("location.href") or ""
    if "zhipin.com" not in url:
        cli.eval(f"location.href='{JOBS_URL}'")
        time.sleep(6)

    base = cli.auth_cookies()
    base_zp = base.get("zp_at", "")
    base_wt = base.get("wt2", "")
    log(f"      基线 zp_at={base_zp[:20]}... wt2={base_wt[:20]}...")
    log("      （登录成功后这两个值必然改变 —— 以此判定『真的登上了』）")

    # 判定当前是否需要登录
    dom = cli.eval(DOM_JS)
    need_login = dom in ("NEED_LOGIN", "RISK_PAGE") or not base_zp
    if need_login:
        log("[3/5] 检测到未登录 —— 打开登录页并置顶窗口")
        if dom == "RISK_PAGE":
            log("      注意：当前是安全验证页，请先完成验证再扫码")
        cli.eval(f"location.href='{LOGIN_URL}'")
        time.sleep(7)
        cli.call("Page.bringToFront")
        log(f"      已打开: {LOGIN_URL}")
        log()
        log("=" * 58)
        log("  请在【浏览器窗口】里扫码登录")
        log("  登录完成后无需操作，我会自动检测（每 3 秒查一次 cookie）")
        log(f"  最长等待 {args.timeout} 秒")
        log("=" * 58)
    else:
        log("[3/5] cookie 已存在，等待值刷新（若已登录可直接下一步）")

    deadline = time.time() + args.timeout
    last_note = 0
    while time.time() < deadline:
        try:
            cur = cli.auth_cookies()
        except Exception as exc:
            log(f"      [warn] 读取失败，重连中: {exc}")
            try:
                cli.ws.close()
            except Exception:
                pass
            time.sleep(2)
            p = pick_page()
            if p:
                cli = Client(connect(p))
            continue

        zp_changed = cur.get("zp_at", "") and cur.get("zp_at", "") != base_zp
        wt_changed = cur.get("wt2", "") and cur.get("wt2", "") != base_wt

        if zp_changed or wt_changed:
            which = []
            if zp_changed:
                which.append("zp_at")
            if wt_changed:
                which.append("wt2")
            log()
            log("=" * 58)
            log(f"  [4/5] 检测到登录凭证已刷新（{', '.join(which)}）—— 登录成功")
            log("=" * 58)
            # 让 Chrome 把 cookie 落盘（避免之前的"登录白登"）
            time.sleep(6)
            if args.keep_open:
                log("      已保留浏览器窗口（--keep-open）")
            else:
                log("[5/5] 优雅关闭浏览器以把 cookie 写入磁盘 ...")
                try:
                    cli.call("Browser.close", timeout=8)
                except Exception:
                    pass
                time.sleep(4)
                log("      完成 —— cookie 已保存，下次启动登录态仍在")
            return 0

        if time.time() - last_note > 60:
            log(f"      [等待中] zp_at={'已变' if zp_changed else '未变'} "
                f"wt2={'已变' if wt_changed else '未变'} ...")
            last_note = time.time()
        time.sleep(3)

    log()
    log(f"[FAIL] 等待 {args.timeout} 秒仍未检测到 cookie 刷新，已退出")
    return 1


if __name__ == "__main__":
    sys.exit(main())
