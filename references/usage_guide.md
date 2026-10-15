# BOSS 直聘自动投递使用手册

> version 23.0.0（通用版）

## 1. 快速开始

### 环境要求

- Windows 10/11
- Python 3.11+（3.10 亦可）
- Chrome
- `websocket-client`

```bash
python -m pip install -r requirements.txt
```

### 四步启动

```bash
# 1. 首次配置：从模板复制一份改，或让 Agent 走引导问答生成
cp templates/frontend.json profile.json

# 2. 启动或复用 CDP Chrome
python scripts/start_cdp_v2.py

# 3. 验证筛选，不投递
python scripts/boss_auto_apply_cdp.py --dry

# 4. 确认当天尚未投递后，正式运行
python scripts/boss_auto_apply_cdp.py
```

`scripts/boss_auto_apply_cdp.py` 是唯一投递入口。

没有 `profile.json` 时脚本会打印引导信息并**拒绝运行** —— 这是有意设计，
避免用错行业的词表跑完一整轮却一个都没投。

## 2. 首次配置

`profile.json` 决定投什么岗位。字段完整说明见 [profile_schema.md](profile_schema.md)。

最小可用配置：

```json
{
  "city": "深圳",
  "keywords": ["前端开发", "React开发", "Vue开发"],
  "score": {
    "base": 45,
    "strong_positive": ["前端开发", "react", "vue"],
    "weak_positive": ["前端", "组件"],
    "negative": ["实习", "销售", "客服"]
  }
}
```

其余字段都有默认值。**`strong_positive` 是关键**：基础分 45 低于阈值 50，
零匹配岗位会被拦掉，要过线必须命中至少一个 `strong_positive`。

配置好后先跑 `--dry`，确认有岗位能过筛选：

```
python scripts/boss_auto_apply_cdp.py --dry
```

若通过数为 0，说明词表与目标岗位不匹配 —— 调整 `score.strong_positive`，
而不是去降低 `score_threshold`。

## 3. CDP Chrome

启动器固定使用：

- 端口：`9223`
- 隔离配置：`UserData-CDP`
- 起始页面：profile 第一个关键词的搜索页

默认行为：

1. 端口已开放则直接复用。
2. 默认不结束任何 Chrome。
3. 检测到 `UserData-CDP` 残留但端口未开放时，提示先手动关闭 CDP 窗口。
4. 只有传入 `--restart` 才重启该隔离实例。

```bash
python scripts/start_cdp_v2.py --restart
```

`--restart` 只处理命令行中包含 `UserData-CDP` 的进程，不影响普通 Chrome。

## 4. 登录与健康检查

不要用 `document.cookie` 检查 BOSS 登录状态。登录凭证是 HttpOnly cookie，页面 JS 读不到。

脚本用 `preflight()` 做功能探测（探针词取 profile 第一个关键词）：

1. 搜索接口必须返回 `code=0`。
2. 必须返回岗位。
3. 至少部分岗位必须带 `salaryDesc`。

如果返回岗位但薪资全空，按风控降级处理并停止本轮。

## 5. 自动投递

### 只筛选

```bash
python scripts/boss_auto_apply_cdp.py --dry
```

`--dry` 会完成接口采集、过滤、评分和通过计数，但不会点击投递。

### 正式运行

```bash
python scripts/boss_auto_apply_cdp.py
```

正式运行前先核实当天数据库记录。默认单轮上限 50、每日上限 100、批间隔 ≥1 小时，
均可在 profile 里调整。

## 6. 过滤链

1. 公司和职位名为空跳过。
2. 公司名 `BOSS直聘` 跳过。
3. `goldHunter=1` 跳过。
4. `blacklist` 命中跳过。
5. 猎头文本、实习、校招、按天计薪跳过。
6. 现场面试或线下面试跳过。
7. `apply_outsourcing=false` 时外包、驻场、外派岗与 `outsource_companies` 跳过。
8. 薪资解析失败、区间上限不达标、下限高于 `salary_max_k` 跳过。
9. 30 天内已投递跳过。
10. 招聘方不在线不再拦截，仅标注 [离线]。
11. 评分低于 `score_threshold` 跳过。
12. `exclude_keywords` / `negative_keywords` 命中跳过。

## 7. 评分

| 维度 | 分值 |
|------|------|
| 基础分 | `score.base`（默认 45） |
| `strong_positive` 命中任一 | +15 |
| `weak_positive` 每命中一个 | +3 |
| `negative` 每命中一个 | -10 |

基础分默认 45 **低于**阈值 50，所以零匹配岗位会被 `LOWSCORE` 拦掉。
无论什么行业，都必须命中至少一个 `strong_positive` 词才能过线。

设计理由（承接 v22.2.14 的教训）：早期版本把「开发」「工程师」这类词放进弱匹配，
它们对任何技术岗都成立，`45 + 3 + 3 = 51` 刚好越线，导致大量方向不符的岗位被投出。
现在这些无区分度词不在任何模板里。

## 8. 配置

全部在 `profile.json`：

| 参数 | 默认值 |
|------|--------|
| `keywords` | **必填** |
| `score` | **必填** |
| `city` | 北京 |
| `max_pages` | 3 |
| `score_threshold` | 50 |
| `salary_min_k` | 14 |
| `salary_max_k` | 35 |
| `salary_floor_k` | 0（不启用） |
| `max_apply` | 50 |
| `daily_limit` | 100 |
| `apply_outsourcing` | true |
| `greeting` | ""（用默认招呼语） |

用 `BOSS_PROFILE` 环境变量可指向别的配置文件，便于多份切换：

```bash
BOSS_PROFILE=profile-上海.json python scripts/boss_auto_apply_cdp.py --dry
```

## 9. 投递报告

```bash
python scripts/boss_report.py
python scripts/boss_report.py --json
```

数据库位置：

```text
data/applications.db
```

该数据库用于 30 天去重，禁止删除或清空。

## 10. 风控处理

出现 `code:37 您的环境存在异常` 或明确安全错误时：

1. 立即停止当前整轮。
2. 不重载、不等待重试、不换关键词绕过。
3. 等待用户确认登录态和环境恢复正常。
4. 是否重新运行由用户决定。

## 11. 运行节奏

- 默认单轮最多 50 个、每日上限 100（平台每日主动沟通上限约 150）。
- 批间隔 ≥1 小时，不要连续刷。
- 间隔为长尾随机：多数 3~5.5 秒，偶尔 8~14 秒或 20~35 秒。
- 采集层已拟人化：关键词顺序随机、每词翻 2~3 页、停顿时长不规则、
  词间约 40% 概率翻看一个岗位详情页、每 4 个词停顿 45~90 秒。
- 连续失败达到 5 次自动熔断。
- 一切以不封号为最高优先级。
