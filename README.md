# bosszhipin-auto-apply (v23 通用版)

BOSS 直聘自动投递工具。通过 CDP 控制本机隔离的 Chrome，完成岗位采集、过滤、评分和招呼语投递。

**适用于任意行业与城市** —— 关键词、城市、薪资门槛、评分词表全部由 `profile.json` 配置，
首次使用时通过一次问答生成。

> v23.0.0

## 特性

| 能力 | 说明 |
|------|------|
| **行业无关** | 关键词/城市/薪资/评分词表全部来自 `profile.json`，附 8 套行业模板 |
| **首次引导** | 缺配置时脚本拒绝运行并给出引导，避免"跑完一个没投" |
| CDP 控制 | 复用本机隔离 Chrome 的真实登录态 |
| 接口式发现 | 调用 `/wapi/zpgeek/search/joblist.json` 获取明文薪资、在线状态和猎头标记 |
| 详情页直投 | 打开 `/job_detail/<id>.html`，校验标题后点击沟通按钮 |
| 边采边投 | 采完一个关键词即投递该词岗位，中断不丢已投记录 |
| 过滤链 | 噪音、猎头、黑名单、实习校招、现场面试、薪资、去重、在线状态、评分和终审保险 |
| 防封号 | 单轮上限可配、长尾随机间隔（拟人节奏）、连续失败熔断 |
| 风控保护 | `code:37` 立即终止整轮，不重试 |
| SQLite | `data/applications.db`，30 天去重 |
| 投递报告 | `scripts/boss_report.py` |

## 环境

- Windows 10/11
- Python 3.11+（3.10 亦可）
- Chrome

```bash
python -m pip install -r requirements.txt
```

## 使用

### 1. 首次配置（只做一次）

脚本读不到 `profile.json` 时会明确拒绝运行并提示缺什么。用 Agent 时会自动走引导问答；
手动配置就从模板复制一份改：

```bash
cp templates/frontend.json profile.json
```

然后改 `keywords`（按优先级排序）、`city`、薪资门槛和 `score` 词表。
各字段含义见 [references/profile_schema.md](references/profile_schema.md)。

可用模板：

| 模板 | 适用方向 |
|------|----------|
| `data.json` | 数据开发 / 数仓 / ETL / BI / 数据分析 |
| `backend.json` | 后端 / Java / Go / Python 服务端 |
| `frontend.json` | 前端 / 全栈 / 小程序 |
| `qa.json` | 软件测试 / 自动化测试 |
| `product.json` | 产品经理 |
| `design.json` | UI / 视觉 / 交互 / 平面设计 |
| `operations.json` | 新媒体 / 内容 / 电商运营 |
| `sales.json` | 销售 / 商务 |

> 非技术方向（财务/法务/医疗/教师等）请基于最接近的模板改写 `keywords` 与
> `score.strong_positive`。`strong_positive` 决定哪些岗位能过评分线，必须含目标岗位核心术语。

### 2. 启动或复用 CDP Chrome

```bash
python scripts/start_cdp_v2.py
```

端口 `9223` 已开放时会直接复用，默认不结束任何 Chrome。只有显式使用下面的命令，才会重启命令行中包含 `UserData-CDP` 的隔离实例：

```bash
python scripts/start_cdp_v2.py --restart
```

### 3. 验证筛选

```bash
python scripts/boss_auto_apply_cdp.py --dry
```

`--dry` 只做采集、过滤、评分和通过计数，不点击投递。**首次配置完务必先跑这个**，
确认有岗位能过筛选再正式投。

### 4. 正式投递

确认当天还没有执行过一轮后：

```bash
python scripts/boss_auto_apply_cdp.py
```

默认单轮最多 50 个，每日上限 100（均可配）。批间隔 ≥1 小时，不要连续刷。

### 5. 查看报告

```bash
python scripts/boss_report.py
python scripts/boss_report.py --json
```

## 配置

全部集中在 `profile.json`。核心字段：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `keywords` | **必填** | 搜索关键词，顺序即优先级 |
| `score` | **必填** | 评分词表（base/strong_positive/weak_positive/negative） |
| `city` | 北京 | 城市名或 9 位编码 |
| `max_pages` | 3 | 每词翻页上限 |
| `score_threshold` | 50 | 评分阈值 |
| `salary_min_k` | 14 | 区间上沿须 > 该值 |
| `salary_max_k` | 35 | 区间下沿高于该值则跳过 |
| `salary_floor_k` | 0 | 0 = 不启用下限门槛 |
| `max_apply` | 50 | 单轮投递上限 |
| `daily_limit` | 100 | 每日投递上限 |
| `apply_outsourcing` | true | 是否投外包岗 |
| `greeting` | "" | 空 = 用 BOSS 默认招呼语 |

可用 `BOSS_PROFILE` 环境变量指向其他配置文件，方便准备多份（如北京/上海各一份）。

## 过滤顺序

1. 公司和职位名不能为空。
2. 公司名 `BOSS直聘` 跳过。
3. `goldHunter=1` 跳过。
4. `blacklist` 命中跳过。
5. 猎头文本、实习、校招、按天计薪和现场面试跳过。
6. `apply_outsourcing=false` 时外包岗与 `outsource_companies` 跳过。
7. 薪资解析失败、区间上限低于门槛、下限高于 `salary_max_k` 时跳过。
8. 30 天内已投递跳过。
9. 招聘方不在线不再拦截，仅标注 [离线]。
10. 评分低于 `score_threshold` 跳过。
11. `exclude_keywords` / `negative_keywords` 命中跳过。

## 评分

| 维度 | 分值 |
|------|------|
| 基础分 | `score.base`（默认 45） |
| `strong_positive` 命中任一 | +15 |
| `weak_positive` 每命中一个 | +3 |
| `negative` 每命中一个 | -10 |

基础分默认 45 **低于**阈值 50，所以零匹配岗位会被拦掉 —— 要过线必须命中至少一个
`strong_positive`。这就是"什么算对口"的判据，配置时务必把目标岗位核心术语放进去。

## 登录与风控

不要用 `document.cookie` 判断登录状态。BOSS 登录凭证是 HttpOnly cookie，前端 JS 无法读取。脚本通过 `preflight()` 功能探测接口、岗位和薪资字段是否正常。

出现 `code:37` 或明确安全错误时立即停止。不要重载、等待后重试或换关键词绕过。

## 项目结构

```text
boss-auto-apply-generic/
├── SKILL.md
├── README.md
├── AGENTS.md
├── requirements.txt
├── profile.json          # 首次引导生成（不入库）
├── templates/            # 8 套行业模板
├── data/applications.db
├── references/
│   ├── profile_schema.md
│   ├── city_codes.md
│   ├── usage_guide.md
│   └── cdp_troubleshooting.md
├── scripts/
│   ├── boss_auto_apply_cdp.py
│   ├── config.py         # profile 加载与校验
│   ├── cdp_utils.py
│   ├── start_cdp_v2.py
│   └── boss_report.py
├── tests/
└── tools/
```

## 安全约束

- 禁止删除或清空 `data/applications.db`。
- 禁止强制结束全部 Chrome。
- 仅供学习和研究，请遵守 BOSS 直聘使用规范。
