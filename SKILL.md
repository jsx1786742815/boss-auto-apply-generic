---
name: bosszhipin-auto-apply
description: Use when the user asks to auto-apply Boss Zhipin (BOSS直聘) jobs through local Chrome CDP. Works for any industry/city via a one-time profile questionnaire. v23 uses the joblist API for discovery, direct job-detail navigation for applications, functional preflight checks, a configurable run cap, and immediate shutdown on risk control.
metadata:
  version: "23.0.0"
  short-description: "首次问答收集偏好后，通过本机 Chrome CDP 自动投递 BOSS 直聘岗位（任意行业/城市）"
---

# bosszhipin-auto-apply (v23 通用版)

通过 Chrome DevTools Protocol 控制本机隔离的 Chrome 配置，自动完成岗位采集、过滤、评分和招呼语投递。

**v23 起本 skill 与行业无关**：关键词、城市、薪资门槛、评分词表和黑名单全部来自
`profile.json`。第一次使用必须先完成下面的「首次引导」，否则脚本会拒绝运行并提示缺什么。

## Skill 根目录

本 Skill 的脚本、数据库和参考资料均位于 `SKILL.md` 所在目录。执行命令前先定位该目录并将其作为工作目录；不要从用户当前项目目录推断相对路径。

首次使用或脚本提示缺少 `websocket` 时，在 Skill 根目录安装依赖：

```bash
python -m pip install -r requirements.txt
```

## 首次引导（必做，只做一次）

**判断依据**：Skill 根目录下**没有** `profile.json` 时，说明这是用户第一次使用。

此时**不要直接跑投递脚本**。按下面顺序和用户对话，收集信息后生成 `profile.json`：

### 第 1 步：先问这 4 件事

一次性问清楚，不要挤牙膏：

| 要问的 | 说明 | 示例 |
|--------|------|------|
| **① 找什么岗位** | 搜索关键词，**按优先级排序**（越想要越靠前）。建议 5~12 个，太宽会捞回噪音 | `数据开发`、`Python后端`、`产品经理` |
| **② 哪个城市** | 常用城市名即可（北京/上海/深圳…）；小城市让用户给 BOSS 的 9 位编码，编码表见 [references/city_codes.md](references/city_codes.md) | `深圳` |
| **③ 薪资范围** | 期望**下限**与**上限**（单位 K）。给「最低能接受多少」和「别超过多少」就够 | 15K ~ 40K |
| **④ 做什么方向** | 用来挑评分词表和排除词。若与内置模板接近，直接套模板再改 | `前端`、`设计`、`运营` |

### 第 2 步：套模板，别让用户从零写词表

`templates/` 里有可直接用的行业模板：

| 模板 | 适用 |
|------|------|
| `data.json` | 数据开发 / 数仓 / ETL / BI / 数据分析 |
| `backend.json` | 后端 / Java / Go / Python 服务端 |
| `frontend.json` | 前端 / 全栈 / 小程序 |
| `qa.json` | 软件测试 / 自动化测试 / 测试开发 |
| `product.json` | 产品经理 / 产品设计 |
| `design.json` | UI / 视觉 / 交互 / 平面设计 |
| `operations.json` | 新媒体 / 内容 / 电商运营 |
| `sales.json` | 销售 / 商务（**注意**：需删掉模板 negative 里的销售词） |

做法：**读最接近的模板 → 用第 1 步收集到的 4 项信息覆盖对应字段 → 写入 `profile.json`**。
用户方向不在表里（如财务、法务、医疗、教师），就基于最接近的模板改写
`keywords` 与 `score.strong_positive` —— 后者决定哪些岗位能过评分线，**必须包含目标岗位的核心术语**。

### 第 3 步：确认后再落盘

把生成的 `profile.json` 关键内容**读回给用户确认**（关键词、城市、薪资、预期能过的岗位类型），
用户认可后写入 Skill 根目录的 `profile.json`。字段完整说明见
[references/profile_schema.md](references/profile_schema.md)。

### 首次引导的常见误区

- **不要静默套用某个行业默认值。** 词表与用户方向不符时，岗位会**全部**掉到基础分
  被 `LOWSCORE` 拦掉，用户只看到"跑完了但一个没投"，极难自查。
- **`score.strong_positive` 不能为空。** 配置层会直接报错。
- **关键词别只写一个。** BOSS 单关键词可捞岗位有限，5~12 个覆盖度才够。
- **销售方向要清空 exclude/negative 里的销售词**，否则销售岗会被自己的排除词拦光。

## 运行入口

```bash
# 启动或复用 CDP Chrome。默认不会结束任何 Chrome。
python scripts/start_cdp_v2.py

# 先做只筛选不投递的验证。首次配置完强烈建议先跑这个。
python scripts/boss_auto_apply_cdp.py --dry

# 确认当天尚未投递后，才执行正式投递。
python scripts/boss_auto_apply_cdp.py

# 查看投递记录。
python scripts/boss_report.py

# 交互式确认登录（投递前推荐跑一次）。
python tools/wait_login.py --timeout 1800
```

`scripts/boss_auto_apply_cdp.py` 是唯一投递入口。

## 当前行为

- 发现层调用 `/wapi/zpgeek/search/joblist.json`，不依赖搜索页 DOM 卡片。
- 投递层直接打开 `/job_detail/<encryptJobId>.html`，校验标题后点击 `a.btn-startchat`。
- 使用 `data/applications.db` 做 30 天去重，禁止删除或清空数据库。
- 关键词顺序即投递优先级；越靠前的词，岗位越先被采集和投递。
- 边采边投：采完一个关键词就立刻投递该词的岗位，中途被风控打断时已投出的记录不丢失。
- 单轮投递上限、每日上限、批间隔均可配置（默认单轮 50、每日 100）。
- 采集层拟人化：每词翻 2~3 页、按长尾分布停顿、导航后模拟滚动、词间随机翻看详情页、每 4 个词歇一次。
- 薪资按区间过滤（阈值来自 profile）；评分阈值来自 profile。
- 默认允许外包、驻场、外派岗位（profile `apply_outsourcing=false` 可关闭）。
- 默认只发送 BOSS 默认招呼语；profile `greeting` 非空时改发自定义招呼语。

## profile.json 字段速查

```jsonc
{
  "city": "深圳",                  // 城市名或 9 位编码
  "keywords": ["数据开发", "ETL"],  // 必填，顺序即优先级
  "score": {                        // 必填
    "base": 45,                     // 基础分，须低于 score_threshold
    "strong_positive": ["spark"],   // 命中任一 +15 —— 对口岗位靠它过线
    "weak_positive": ["sql"],       // 每命中一个 +3
    "negative": ["销售"]            // 每命中一个 -10
  },
  "max_pages": 3,
  "max_apply": 50,
  "daily_limit": 100,
  "score_threshold": 50,
  "salary_min_k": 14,               // 区间上沿须 > 该值
  "salary_max_k": 35,               // 区间下沿高于该值则跳过
  "salary_floor_k": 0,              // 0 = 不启用「起薪不得低于 N K」
  "apply_outsourcing": true,
  "blacklist": [],
  "outsource_companies": [],
  "exclude_keywords": [],
  "negative_keywords": [],
  "greeting": ""
}
```

## 启动器规则

`start_cdp_v2.py` 的行为是：

1. 如果 `127.0.0.1:9223` 已开放，直接复用，不结束任何 Chrome。
2. 如果检测到 `UserData-CDP` 残留进程但端口未开放，默认退出并提示手动处理。
3. 只有显式传入 `--restart` 时，才结束命令行中包含 `UserData-CDP` 的 Chrome 进程并重启隔离实例。
4. 不强制结束普通 Chrome，也不结束隔离实例之外的任何浏览器进程。

## 登录与健康检查

不要在页面 JavaScript 中检查 `document.cookie` 来判断登录。BOSS 的登录凭证是 HttpOnly cookie，前端 JS 读不到，这类判断会误报未登录。

`preflight()` 做功能探测（探针词取 profile 的第一个关键词）：

1. 从 `zhipin.com` 页面上下文请求 `joblist.json`。
2. 要求 `code=0`。
3. 要求返回岗位。
4. 要求至少部分岗位带 `salaryDesc`。

任一项失败就停止本轮。若返回岗位但薪资全空，按 BOSS 风控降级处理，不要继续投递。

人工登录用 `tools/wait_login.py`：用 CDP `Network.getCookies` 读 HttpOnly 凭证作基线（纯本地读取，
零网络请求），轮询对比 cookie 值，值被服务端刷新即代表登录真正生效；检测到刷新后主动发
`Browser.close` 优雅关闭，让 Chrome 把 cookie flush 到磁盘，再由投递任务重新拉起 ——
否则 Chrome 作为子进程被宿主强杀会导致 cookie 丢失（"登录白登"）。

禁止用「页面文本不含『登录/注册』」判断登录：页面停在 `/passport/zp/verify.html`
（安全验证页）时该页本来就没有这行字，会误判为已登录。
禁止用高频 `fetch` 轮询接口探测登录态 —— 等于高频注入 XHR，会把 `code_35` 顶成 `code_37`。

需要排查 CDP、端口或登录状态时，再读取 [references/cdp_troubleshooting.md](references/cdp_troubleshooting.md)。需要完整运行、配置和报告说明时，读取 [references/usage_guide.md](references/usage_guide.md)。

## 风控红线

接口返回 `code:37 您的环境存在异常` 或明确的安全错误时：

- `collect_all()` 立即抛出 `RiskControlError`。
- 主流程立即结束整轮。
- 不重载、不等待后重试、不换关键词绕过。
- 等待用户确认环境恢复后再决定是否重新运行。

## 固定过滤链

以下 1~5、7~8 项与行业无关，始终生效；6、9~11 项由 profile 驱动：

1. 空职位名或空公司名跳过。
2. 公司名为 `BOSS直聘` 跳过。
3. `goldHunter` 猎头岗跳过。
4. profile `blacklist` 命中跳过。
5. 猎头文本、实习、校招、按天计薪、现场面试跳过。
6. `apply_outsourcing=false` 时，profile `outsource_companies` 与外包词跳过。
7. 薪资解析失败、区间上限不达标、区间下限超标跳过。
8. 30 天内已投递记录跳过。
9. BOSS 不在线不再拦截，仅标注 [离线]。
10. 评分低于 `score_threshold` 跳过。
11. profile `exclude_keywords` / `negative_keywords` 命中跳过。

## CDP 注意事项

- 本机代理变量可能让 `127.0.0.1:9223` 请求误走代理。投递脚本已在进程内清除代理变量并设置 `NO_PROXY`。
- 端口不可用时先重新运行 `python scripts/start_cdp_v2.py`。只有确认残留进程属于 `UserData-CDP` 时才使用 `--restart`。
- 仅供学习和研究，请遵守 BOSS 直聘使用规范。
