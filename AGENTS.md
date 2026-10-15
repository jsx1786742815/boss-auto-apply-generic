# AGENTS.md - Agent 项目说明

BOSS 直聘自动投递工具（v23.0.0，通用版）。当前唯一投递入口是 `scripts/boss_auto_apply_cdp.py`。

## 首次使用（最重要）

**Skill 根目录下没有 `profile.json` = 用户第一次使用。**

此时不要直接跑投递脚本 —— 脚本会打印引导信息后退出。正确做法是按 `SKILL.md`
的「首次引导」章节，向用户收集 4 项信息（岗位关键词、城市、薪资范围、行业方向），
套用 `templates/` 里最接近的模板，生成 `profile.json`，经用户确认后落盘。

v23 起关键词/城市/薪资/评分词表全部来自 `profile.json`，Python 代码里**不再有**
任何行业的硬编码默认值。**不要**为了方便而把某个行业的词表写回代码。

## 项目结构

```text
boss-auto-apply-generic/
├── SKILL.md                 # Agent 使用说明（含首次引导）
├── README.md
├── AGENTS.md
├── requirements.txt
├── profile.json             # 首次引导生成，已在 .gitignore 中
├── templates/               # 8 套行业模板
├── data/applications.db
├── references/
│   ├── profile_schema.md
│   ├── city_codes.md
│   ├── usage_guide.md
│   └── cdp_troubleshooting.md
├── scripts/
│   ├── boss_auto_apply_cdp.py
│   ├── config.py            # profile 加载与校验
│   ├── cdp_utils.py
│   ├── start_cdp_v2.py
│   └── boss_report.py
├── tests/
└── tools/
```

## 标准操作流程

### 0. 确认 profile 存在

```bash
ls profile.json
```

不存在就先走首次引导。

### 1. 安装依赖

```bash
python -m pip install -r requirements.txt
```

要求 Python 3.11+（3.10 亦可）。

### 2. 启动或复用 CDP Chrome

```bash
python scripts/start_cdp_v2.py
```

- 端口 `9223` 已开放时直接复用。
- 默认不结束任何 Chrome。
- `UserData-CDP` 残留且端口未开放时，先提示用户手动关闭该 CDP 窗口。
- 只有显式 `--restart` 才结束命令行中包含 `UserData-CDP` 的进程。
- 禁止强制结束任何 Chrome 进程。

### 3. 先做 dry run

```bash
python scripts/boss_auto_apply_cdp.py --dry
```

检查接口健康、关键词采集和过滤结果。`--dry` 不点击投递。

**若 dry run 显示通过数为 0**，八成是 `score.strong_positive` 与用户方向不匹配 ——
回到 profile 调整词表，而不是去放宽阈值。

### 4. 正式投递

```bash
python scripts/boss_auto_apply_cdp.py
```

只有在用户明确要求，且确认当天尚未执行过一轮时才能运行。

### 5. 查看报告

```bash
python scripts/boss_report.py
```

## 红线

1. 默认单轮上限 50、每日上限 100，批间隔 ≥1 小时。运行前先核实当天数据库记录。
2. 出现 `code:37 您的环境存在异常` 或安全错误时立即终止整轮，不重载、不等待重试、不换关键词绕过。
3. 严禁删除或清空 `data/applications.db`。30 天去重依赖该数据库。
4. 不要强制结束 Chrome 进程。
5. 不要在 shell 中注入 `HTTP_PROXY` 或 `HTTPS_PROXY` 后运行脚本；脚本已自行清理代理变量。
6. 不要把用户个人配置（`profile.json`）提交到仓库。

## 当前关键实现

- `config.load_profile()` 读 `profile.json` 并校验；缺失/非法时抛 `ProfileError`，信息即引导话术。
- `boss_auto_apply_cdp.configure(profile)` 把配置写入模块级 `_CFG`，供过滤/评分函数读取。
- `get_ws_url()` 优先选择 `zhipin.com` 页面。
- `ensure_zhipin_page(cdp, city_code, keyword)` 在 preflight 前把 CDP 页面放到 BOSS 域名下。
- `preflight()` 做功能探测，不检查前端 cookie；探针词取 profile 第一个关键词。
- `collect_all()` 调用 `joblist.json`，`code:37` 抛出 `RiskControlError`。
- `apply_via_detail()` 打开详情页，校验职位标题后点击 `a.btn-startchat`。
- `score_job()` 完全按 profile 词表打分，无内置行业词。

## 验证

```bash
python -m unittest discover -s tests -v
python -m py_compile scripts/*.py
```

禁止仅为了验证而执行正式投递。必要时最多执行 `--dry`。
