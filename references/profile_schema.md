# profile.json 字段说明

`profile.json` 放在 Skill 根目录，是**唯一**决定投什么岗位的文件。
第一次使用时由 Agent 通过引导问答生成（见 `SKILL.md` 的「首次引导」）。

也可用环境变量 `BOSS_PROFILE` 指向任意路径，便于多份配置切换（如 `profile-北京.json` / `profile-上海.json`）。

## 必填字段

### `keywords` — 搜索关键词

```json
"keywords": ["数据开发", "数据仓库", "ETL", "BI开发", "数据分析"]
```

- 字符串数组，**顺序即优先级**：越靠前的词，岗位越先被采集、越先被投递。
- 建议 5~12 个。太少覆盖不足；太宽（如只写「开发」）会捞回大量噪音，全靠评分拦截。
- 中途若被风控打断，靠前的关键词已经先投出去了 —— 所以把最想要的方向放前面。

### `score` — 评分词表

```json
"score": {
  "base": 45,
  "strong_positive": ["数据开发", "etl", "数仓", "spark"],
  "weak_positive": ["sql", "python"],
  "negative": ["销售", "客服", "实习"]
}
```

评分公式（词表在匹配时统一转小写，`text` = 职位名 + 薪资 + 公司名）：

| 项 | 规则 |
|----|------|
| `base` | 基础分，默认 45 |
| `strong_positive` | 命中**任意一个** +15（只加一次） |
| `weak_positive` | 每命中一个 +3 |
| `negative` | 每命中一个 -10 |

最终分数钳制在 0~100，`< score_threshold` 的岗位被 `LOWSCORE` 拦掉。

**关键**：`base` 默认 45 低于阈值 50，所以**零匹配岗位会出局**。
要过线必须命中至少一个 `strong_positive`（45 + 15 = 60）或叠加足够多弱匹配。
因此 `strong_positive` **必须放目标岗位的核心术语**，它是"什么算对口"的唯一判据。

## 选填字段

### `city`

城市名或 BOSS 的 9 位编码。支持的城市名见 [city_codes.md](city_codes.md)。
写 `"北京市"` 也能识别。未收录的县城请直接填 9 位编码。

### 薪资门槛

| 字段 | 默认 | 含义 |
|------|------|------|
| `salary_min_k` | 14 | 区间**上沿**必须 `>` 该值（即默认要求上沿 ≥15K） |
| `salary_max_k` | 35 | 区间**下沿** `>` 该值则跳过（挡住"35K 起"这种超预期岗） |
| `salary_floor_k` | 0 | 0 = 不启用；填 N 则区间下沿 `< N` 时跳过（"起薪不得低于 N K"） |

薪资单位统一为 K。区间写成 `22000-40000元` 这类绝对值时，脚本按数量级自动折算成 K。

### 数量与节奏

| 字段 | 默认 | 含义 |
|------|------|------|
| `max_pages` | 3 | 每个关键词最多翻几页（实际随机取 2~max_pages） |
| `max_apply` | 50 | 单轮投递上限 |
| `daily_limit` | 100 | 每日投递上限（跨轮累计，读数据库当日记录） |
| `score_threshold` | 50 | 评分通过线 |

> BOSS 每日主动沟通上限约 150。默认单轮 50、每日 100 已留余量，
> 不建议调高；批间隔应 ≥1 小时。

### 公司与岗位排除

| 字段 | 含义 |
|------|------|
| `blacklist` | 永久黑名单，命中即跳过，无论外包开关如何 |
| `outsource_companies` | 外包/人力服务商名单，仅 `apply_outsourcing=false` 时拦截 |
| `exclude_keywords` | 职位名命中即跳过（终审，在评分之后） |
| `negative_keywords` | 职位名命中即跳过（终审，大小写不敏感） |

`exclude_keywords` 与 `negative_keywords` 功能相同，只是分开写便于归类
（前者放"业务上不要的岗位类型"，后者放"方向不符的技术栈"）。

### 其他

| 字段 | 默认 | 含义 |
|------|------|------|
| `apply_outsourcing` | `true` | `false` 时外包岗直接跳过并收窄黑名单 |
| `allow_offline_boss` | `true` | 预留开关；目前招聘方离线岗照投，仅标注 `[离线]` |
| `greeting` | `""` | 空 = 只用 BOSS 默认招呼语；非空则填入弹窗输入框后发送 |

## 完整示例

```json
{
  "city": "深圳",
  "keywords": ["前端开发", "React开发", "Vue开发", "Web前端", "全栈开发"],
  "max_pages": 3,
  "max_apply": 50,
  "daily_limit": 100,
  "score_threshold": 50,
  "salary_min_k": 12,
  "salary_max_k": 45,
  "salary_floor_k": 0,
  "apply_outsourcing": true,
  "allow_offline_boss": true,
  "score": {
    "base": 45,
    "strong_positive": ["前端开发", "web前端", "react", "vue", "typescript", "next.js"],
    "weak_positive": ["前端", "组件", "性能优化", "工程化"],
    "negative": ["实习", "应届", "销售", "客服", "java", "php", "运维", "测试"]
  },
  "blacklist": [],
  "outsource_companies": [],
  "exclude_keywords": ["高提成", "电话销售", "客户经理"],
  "negative_keywords": ["培训讲师", "课程顾问"],
  "greeting": ""
}
```

## 配置报错怎么读

脚本读不到或读不懂配置时，会直接打印引导信息并**拒绝运行**，例如：

```
!! 未找到可用的个人配置
未找到配置文件：/path/to/profile.json
  这是本 skill 的首次使用引导：请向用户收集以下信息，然后生成 ...
```

常见报错：

| 报错 | 处理 |
|------|------|
| `未找到配置文件` | 走 `SKILL.md` 的首次引导流程 |
| `缺少必填字段「keywords」` | 补 `keywords` 数组 |
| `缺少必填字段「score」` | 补 `score` 对象 |
| `score.strong_positive 为空` | 至少填一个目标岗位核心术语 |
| `无法识别城市「X」` | 换成常用城市名或 9 位编码 |
| `配置文件不是合法 JSON` | 检查逗号/引号；JSON 不支持注释和尾逗号 |
