# CDP 连接问题排查

## 1. 无法连接 9223

现象：

```text
urllib.error.URLError: [WinError 10061]
```

处理：

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 9223
python scripts/start_cdp_v2.py
```

启动器默认复用现有 CDP 实例，不会结束任何 Chrome。

## 2. 检测到 UserData-CDP 残留

如果启动器提示检测到 `UserData-CDP` 进程，但端口未开放：

1. 优先手动关闭该 CDP Chrome 窗口。
2. 确认残留进程确实属于隔离的 `UserData-CDP` 后，才使用：

```bash
python scripts/start_cdp_v2.py --restart
```

不要强制结束全部 Chrome，也不要结束普通 Chrome。

## 3. WebSocket 连接中断

现象：

```text
ConnectionAbortedError: [WinError 10053]
```

可能原因：

- CDP Chrome 被关闭。
- 端口被其他进程占用。
- 系统回收了子进程。

处理：

1. 检查 9223 是否开放。
2. 重新运行 `python scripts/start_cdp_v2.py`。
3. 如果 CDP Chrome 已退出，启动器会创建新的隔离实例。

## 4. HTTP 代理拦截本地 CDP

现象：

```text
502 Bad Gateway
```

原因：shell 中的 `HTTP_PROXY` 或 `HTTPS_PROXY` 把 `127.0.0.1:9223` 请求也发给了代理。

处理：

- 不要在注入代理变量后运行脚本。
- 投递脚本已经在进程内清除代理变量并设置 `NO_PROXY=127.0.0.1,localhost,::1`。
- WebSocket 连接显式设置 `http_no_proxy`。

## 5. 页面没有可用 CDP target

现象：

```text
Chrome CDP 没有可用页面
```

处理：

1. 确认 Chrome 至少打开一个普通标签页。
2. 重新运行 `python scripts/start_cdp_v2.py`。
3. 不要通过强杀全部 Chrome 来修复。

## 6. 接口返回 code:35 / code:37（风控）

现象：

```text
code:37 您的环境存在异常
```

此外还有 `code_35 您的IP地址存在异常行为`，页面会跳 `/passport/zp/verify.html`（极验验证页）。

这类码是风控信号，但**不一定**是 IP 被标记需要冷却 —— 0917 实测最常见的原因是
**登录态失效**（判定方法见第 7 节）。

处理：

1. **先排查登录态**（第 7 节）—— 多数情况重新登录即恢复，接口立刻回到 30 条带薪资。
2. 登录态正常仍报码，才按风控冷却处理：当前整轮立即结束，不重载、不等待重试、
   不更换关键词绕过。
3. **严禁高频 fetch 探测接口** —— 每 4 秒探测一次本身就是"高频注入 XHR"，
   0917 实测把 `code_35` 顶成了 `code_37`。需要探测时改用 CDP 本地命令（见第 10 节）。

## 7. 岗位薪资全空 / 降级返回 15 条

现象：接口返回岗位，但 `salaryDesc` 全为空（常见只返回 15 条）。

**根因优先级：登录态失效 > 风控降级。**

排查（按顺序）：

1. 读 **HttpOnly cookie 值**，不要读页面文本。用 CDP `Network.getCookies`
   取 `zp_at` / `wt2`（纯本地读取，零网络请求）。
2. 让用户重新登录，对比登录前后的 `zp_at` / `wt2`：
   - **值变了** → 登录真的成功（服务端签发新 token 必然改变其值）
   - **值没变** → 登录没生效，或 cookie 没写盘（见第 10 节）
3. 登录态恢复后再跑 `--dry`，接口应恢复「30 条、带薪资 30 条」。

**坑（0917 实测误判两次）**：不要用「页面文本不含『登录/注册』」判断登录 ——
页面停在 `/passport/zp/verify.html`（安全验证页）时，该页文本本来就没有这行字，
会被**误判为已登录**，导致投递白跑。

## 8. 详情页找不到沟通按钮

现象：返回 `NO_BUTTON`。

可能原因：

- 岗位已关闭或下线。
- 按钮尚未加载。
- 页面结构变化。
- 岗位已沟通。

当前脚本会等待页面、校验标题并读取按钮状态。若持续出现，只记录结果，不要通过提高投递频率或连续重试解决。

## 9. 安全边界

- 启动器不强制结束普通 Chrome。
- 默认不结束任何 Chrome。
- `--restart` 只处理 `UserData-CDP` 隔离实例。
- `code:37` 不重试。
- 单轮最多 50，建议每天 2 轮（合计 100，平台每日上限约 150），批间隔 ≥1 小时。
- `data/applications.db` 禁止删除或清空。

## 10. 登录成功后 cookie 丢失（"每次登录都白登"）

现象：用户反复扫码登录，但下次启动浏览器仍是未登录；
`zp_at` / `wt2` 的**值一字未变** —— 说明登录凭证从未写入磁盘。

根因：`start_cdp_v2.py` 用 `subprocess.Popen` 启动 Chrome，Chrome 是脚本的**子进程**。
后台任务（bash）结束时宿主会回收整个进程树，Chrome 被 `TerminateProcess` **强杀**。
Chrome 的 cookie 是**异步写盘**的 —— 强杀 = 未 flush = 凭证丢失。
用户视角就是"登录完浏览器闪退"，且怎么登都登不上。

处理（`tools/wait_login.py` 已实现该方案）：

1. 登录判据改为 **HttpOnly cookie 值对比**（`zp_at` / `wt2`），
   用 CDP `Network.getCookies` 读取 —— **零网络请求**，不产生风控暴露。
2. 检测到值刷新后 `sleep 6` 让 cookie 落盘，
   再主动发 **`Browser.close`**（优雅关闭，Chrome 正常退出会 flush cookie）。
3. 之后再启动投递脚本，登录态即持久化。

验证方法：登录后重启浏览器再读一次 cookie —— 值应为**新值**，
且会出现登录后才有的 `bst` cookie。

配套约束：

- 隔离 Chrome 必须与投递脚本写在**同一条命令**里执行
  （`start_cdp_v2.py > /dev/null && sleep 3 && python -u boss_auto_apply_cdp.py`）。
- 需要长期保活供人工扫码时，用长驻进程（wait_login）而不是 `sleep` 占位。
- 每次任务结束都会强杀 Chrome，所以**任何需要保留的状态都必须在任务内主动落盘**。
