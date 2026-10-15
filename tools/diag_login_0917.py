# -*- coding: utf-8 -*-
"""诊断登录态：读 CDP 层 cookie（含 HttpOnly）判断是否真掉登录。"""
import json, sys, io, time, urllib.request
import websocket

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
req = urllib.request.Request('http://127.0.0.1:9223/json/list')
pages = json.loads(opener.open(req, timeout=5).read().decode())
tgt = None
for p in pages:
    if p.get('type') == 'page' and 'zhipin.com' in str(p.get('url') or ''):
        tgt = p
        break
if not tgt:
    tgt = pages[0]

ws = websocket.create_connection(tgt['webSocketDebuggerUrl'], timeout=20,
                                 http_no_proxy=['127.0.0.1', 'localhost', '::1'])
_mid = [0]


def send(method, params=None):
    _mid[0] += 1
    ws.send(json.dumps({"id": _mid[0], "method": method, "params": params or {}}))
    deadline = time.time() + 20
    while time.time() < deadline:
        r = json.loads(ws.recv())
        if r.get("id") == _mid[0]:
            return r
    return None


send("Network.enable")
r = send("Network.getCookies", {"urls": ["https://www.zhipin.com"]})
cookies = (r or {}).get("result", {}).get("cookies", [])
print(f"### zhipin.com cookie 共 {len(cookies)} 个")
KEY = ('zp_at', 'wt2', 'token', 'geek_zp_token', 'atoken', 'bst', 'zp_uid', '__zp_stoken__', 't', 'ctoken')
hit = []
for c in cookies:
    n = c.get('name', '')
    v = str(c.get('value') or '')
    if n.lower() in [k.lower() for k in KEY] or 'token' in n.lower() or n in ('zp_at', 'wt2'):
        hit.append((n, v[:40], c.get('httpOnly'), c.get('expires')))
if hit:
    print("### 关键 cookie:")
    for n, v, ho, ex in hit:
        print(f"  {n:20s} = {v:42s} httpOnly={ho} exp={ex}")
else:
    print("### 未发现登录相关关键 cookie —— 确认未登录")
print("### 全部 cookie 名:")
print("  " + ", ".join(sorted(c.get('name', '') for c in cookies))[:900])

# 页面层面再确认
r2 = send("Runtime.evaluate", {"expression": """(() => {
  const t = document.body ? document.body.innerText : '';
  return JSON.stringify({
    hasLoginBtn: /登录\\/注册|立即登录/.test(t),
    hasUserName: !!document.querySelector('.nav-figure, .user-nav, [class*=user-name]'),
    snippet: t.slice(0, 150)
  });
})()""", "returnByValue": True})
print("### 页面登录元素:", (r2 or {}).get("result", {}).get("result", {}).get("value"))
ws.close()
