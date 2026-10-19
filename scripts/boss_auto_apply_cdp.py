# -*- coding: utf-8 -*-
"""
BOSS直聘 自动投递脚本 v23.0 (通用版: 接口发现 + 详情页直投)
=================================================================
v23.0 通用化（本次改造）
- 关键词、城市、薪资门槛、评分词表、黑名单全部移出代码，改由 profile.json 提供，
  经 config.load_profile() 校验后用 configure() 注入模块级 _CFG。
- 删除全部行业硬编码：原 keywords / BLACKLIST_ALWAYS / BLACKLIST_OUTSOURCE /
  score_job 内的数据行业词表 / main() 内的纯 Java·数据治理·销售话术终审词表，
  以及 cdp_utils 里的 DEFAULT_CITY_CODE、DEFAULT_KEYWORD。
- 缺 profile 时不再静默套用默认行业，而是抛 ProfileError 并打印首次引导话术 ——
  否则方向不符的用户会看到"跑完一个没投"却查不出原因。
- 新增 templates/ 八套行业模板与 references/profile_schema.md。
- 新增 profile.greeting：非空时在沟通弹窗填入自定义招呼语。
- 下列 v22.x 版本记录保留，作为评分与风控设计的由来参考（其中的具体数值
  现在是 profile 默认值，不再是代码常量）。

v22.2.14 薪资上沿门槛回到 16K + 修复泛化弱匹配词（2026-09-15）
- 薪资：min_salary_k 17 → 15，即【上沿 ≥16K 即可】。0915 实测 18K 门槛把 ETL(31/42)、
  数据开发(52/86) 的对口岗位大量砍掉（多为 4-6K/10-15K/12-15K），ETL 因此零投出。
- 评分：weak_positive 移除 '开发'/'工程师'/'java'。这三个词无区分度，
  45 + 3 + 3 = 51 刚好越过阈值 50，导致「全栈开发工程师」「AI应用开发工程师」
  「资深后端开发工程师」「MES开发工程师」等 15 个无关岗位被投出（0915 实测）。
  移除后它们掉回 45 分被拦；对口岗位仍由强匹配词（+15）兜底，不误杀。

v22.2.13 薪资上沿门槛 16K → 18K（2026-09-14 用户指令：上沿调到 18K）
- min_salary_k 16 → 18：区间上沿必须 ≥18K（原 ≥17K）。
- 代价极小：0914 实跑 50 个中仅 4 个（上沿=17K）会被新门槛刷掉，命中率降 8%。
- 语义：BOSS 要求 16K，上沿门槛 18K 留 2K 余量，避免投到"最高才 17K"的低价值岗位。
- salary_floor_k 仍为 0（不启用下限门槛），max_salary_k = 35 不变。

v22.2.12 撤回薪资下限门槛（2026-09-12 用户指令："还是放宽吧"）
- v22.2.11 曾加 salary_floor_k = 15（区间下限须 ≥15K），实测会连 12-18K / 13-20K
  这类"上沿达标、起薪偏低"的岗位一起拦掉，可投量下降明显，用户要求放宽。
- 现置 salary_floor_k = 0 表示【不启用】下限门槛（判定条件恒不成立），
  恢复 v22.2.10 的口径：只卡上沿（须 > 16K，即 ≥17K）+ 下限不得高于 35K。
- 参数保留为开关：将来若需"起薪不得低于 N K"，把 0 改回 N 即可。

v22.2.5 拟人化节奏（2026-09-11，BOSS 要求"改得像人一点"）
- 核心认知：风控识别的不只是"请求总量"，更是"节奏特征"。等距轮询是机器指纹。
- 新增 human_delay() 长尾延迟：70% 快速(2~4.5s) / 22% 停留看内容(6~14s) / 8% 短暂离开(20~45s)。
- 新增 human_scroll()：每次导航后在页面模拟 1~2 次真人滚动。
- collect_all：关键词顺序随机打乱；每词翻页数随机 2~max_pages；
  词间约 40% 概率点开一个岗位详情页停留 4~9s 再退回列表；每 4 个词停顿 45~90s。
- 投递间隔同样改长尾分布（3~5.5s 为主，偶尔 8~14s / 20~35s）。
- 预期：搜索请求 36 → 约 30 次且间隔不再规律；采集总耗时由约 4 分钟升至 7~10 分钟。

v22.2.4 降低采集强度（2026-09-11，因采集中途触发 code:37）
- 关键词 14 → 12：去掉 'Spark'、'离线数仓'（与 '大数据'、'数仓' 语义重叠，采回岗位大量重复）。
- max_pages 5 → 3：单轮接口请求量 70 → 36 次（约 -49%）。
- 翻页间隔 0.8~1.6s → 2.5~4.0s；词间导航间隔 3.5~5.0s → 5.0~7.5s，节奏更接近真人浏览。

v22.2.3 薪资门槛 15K → 16K（2026-09-11 用户指令：最低要求 16K）
- min_salary_k 由 15 调为 16：薪资区间上限够不到 16K 的岗位（如 10-15K、12-15K）不再投。
  区间上沿 ≥16K 的（12-16K / 12-18K / 15-20K 等）保留。

v22.2.2 恢复离线放宽（2026-09-11 用户指令）
- 撤销 v22.2 的"BOSS 不在线即跳过"，恢复 v20/0807 的放宽：离线岗照投，仅日志标注 [离线]。
  理由：主动沟通的招呼消息在直聘侧留存，HR 上线后仍可见，拦截只会白白减少投递量。

v22.2.1 本地修复（2026-09-11）
- 终审保险 SALES_TALK 杀词中的单字 '信贷' 拆成复合销售词
  （信贷专员/信贷销售/信贷经理/信贷业务/信贷员/信贷电销/信贷推广/信贷客服）。
  原单字 '信贷' 与关键词池 '信贷数据'、评分强匹配词 '信贷'（+15）直接冲突：
  实测"信贷数据分析师"71 分、"银行信贷数据开发工程师"77 分，均高于阈值 50，
  却全部被 SALES_TALK 当销售话术岗拦掉，导致 '信贷数据'/'银行数据' 两词产出被清空。

v22.2 外包放宽（2026-09-11 用户指令：外包也投）
- 新增配置开关 APPLY_OUTSOURCING（默认 True）：
  * 黑名单拆分为 BLACKLIST_ALWAYS（垃圾公司，永远拦）与
    BLACKLIST_OUTSOURCE（外包大厂 ≈60 家，仅 APPLY_OUTSOURCING=False 时拦）；
  * is_outsource 关键词闸（外包/驻场/外派/派遣/劳务…）放宽时跳过；
  * 评分负分词移除外包/驻场/派遣/劳务（否则外包词 -10 会把部分岗压到 50 阈值以下被 LOWSCORE 拦死）。
- 关闭开关（False）即恢复 v22.1 原行为。

v22 核心改造（根因：0910 有 7 个关键词误报"0 卡片"，实测每个都有 30 个岗位）

[v21 的问题]
1. 发现层靠 DOM 抓 .job-card-box。BOSS 是 SPA，关键词连续切换时列表常
   来不及重新渲染 → 抓 0 张卡 → 脚本判定"没有岗位"直接跳词。
   0910 因此漏掉 Spark/报表开发/BI开发/帆软/监管报送/银行数据/信贷数据
   共 7 个词（≈210 个岗位），且这 7 个恰好是用户简历最对口的词。
2. 投递靠"回列表页点卡片"，跨页/重渲染时易 CARD_NF，还要三重防串号。
3. 薪资靠 v21.2 的 joblist 二次 fetch 回填，命中率不稳。

[v22 做法]
- 发现层改走 joblist 接口（明文 salaryDesc / bossOnline / goldHunter 全在），
  不再依赖 DOM 渲染时机。接口空返回才判定该页到底。
- 投递层改为直接打开 /job_detail/<encryptJobId>.html 详情页 → 校验标题 →
  点 a.btn-startchat。天然不存在"串号"（人在目标职位页上），也不需要回列表。
- 移除对 DOM 卡片数的任何依赖。

[过滤链变更（0910 用户反馈：投得太少）]
- 薪资：由"下限<15K 就拒"改为"上限<15K 才拒"。即 12-18K / 14-19K 这类
  区间上沿够 15K 的岗位不再被误杀（0910 此项误杀 35 个，占全部拒绝量首位）。
- 评分阈值：60 → 50（神策数据 20-30K、阜外医院 20-35K 曾被 53 分误杀）。
- 保留：黑名单/猎头/实习校招/现场面试/外包/30天去重/BOSS离线/终审保险。
"""
import websocket
import json
import time
import urllib.request
import urllib.parse
import sqlite3
import os
import re
import random
from datetime import datetime, timedelta

from cdp_utils import build_search_url, ensure_zhipin_page, pick_cdp_page
from config import ProfileError, load_profile, profile_path

# ------------------------------------------------------------------
# 本机 shell 注入了 HTTP_PROXY/HTTPS_PROXY=http://127.0.0.1:50341。
# urllib 会把发往 127.0.0.1:9223（Chrome 调试端口）的请求也丢给该代理
# -> HTTP 502 Bad Gateway；websocket-client 握手同样会被代理劫持。
# 本脚本只需访问本地 CDP，不需要任何代理 —— 进程内直接清空。
for _pv in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
            'ALL_PROXY', 'all_proxy'):
    os.environ.pop(_pv, None)
os.environ['NO_PROXY'] = os.environ['no_proxy'] = '127.0.0.1,localhost,::1'

FONT_MAP = {'\ue031': '0', '\ue032': '1', '\ue033': '2', '\ue034': '3', '\ue035': '4', '\ue036': '5', '\ue037': '6', '\ue038': '7', '\ue039': '8', '\ue03a': '9'}


# v22.2.5 拟人化参数
HUMAN_BATCH = 4          # 每处理多少个关键词插入一次长停顿


def human_delay(fast=(2.0, 4.5), slow=(6.0, 14.0), away=(20.0, 45.0),
                p_fast=0.70, p_slow=0.92):
    """拟人化停顿：返回操作之间的等待秒数。

    刻意做成非等距的长尾分布 —— 约 70% 快速操作、22% 停下来看内容、
    8% 短暂离开（接水/接电话）。等距轮询是最典型的机器特征，
    长尾节奏才接近真人。
    """
    r = random.random()
    if r < p_fast:
        return random.uniform(*fast)
    if r < p_slow:
        return random.uniform(*slow)
    return random.uniform(*away)


def human_scroll(cdp, times=None):
    """在页面上模拟 1~2 次真人滚动（纯页面交互，不产生接口请求）。

    拟人动作属于"锦上添花"，失败不应中断采集，故整体容错。
    """
    try:
        for _ in range(times or random.randint(1, 2)):
            cdp.send("Input.dispatchMouseEvent", {
                "type": "mouseWheel",
                "x": random.randint(320, 900),
                "y": random.randint(200, 620),
                "deltaX": 0,
                "deltaY": random.randint(320, 900),
            })
            time.sleep(random.uniform(0.4, 1.3))
    except Exception:
        pass


class RiskControlError(RuntimeError):
    """BOSS 已明确返回风控信号，必须立即结束当前整轮。"""


def decode_font(text):
    if not text: return text
    for enc, digit in FONT_MAP.items(): text = text.replace(enc, digit)
    return text

def get_ws_url():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request('http://127.0.0.1:9223/json/list')
    with opener.open(req, timeout=5) as resp:
        pages = json.loads(resp.read().decode())
    page = pick_cdp_page(pages)
    if not page:
        raise RuntimeError('Chrome CDP 没有可用页面')
    return page['webSocketDebuggerUrl']

class CDP:
    def __init__(self, url):
        self.url = url
        self.ws = None
        self.mid = 0
        self.connect()

    def connect(self):
        for attempt in range(3):
            try:
                self.ws = websocket.create_connection(
                    self.url, timeout=20,
                    http_proxy_host=None,
                    http_no_proxy=['127.0.0.1', 'localhost', '::1'])
                return True
            except:
                time.sleep(1)
        return False

    def send(self, method, params=None):
        for attempt in range(3):
            try:
                self.mid += 1
                msg = {"id": self.mid, "method": method}
                if params: msg["params"] = params
                self.ws.send(json.dumps(msg))
                deadline = time.time() + 20
                while time.time() < deadline:
                    resp = json.loads(self.ws.recv())
                    if resp.get("id") == self.mid:
                        return resp
                return None
            except:
                print(f"    [CDP retry {attempt+1}]")
                time.sleep(1)
                try: self.ws.close()
                except: pass
                self.connect()
        return None

    def eval(self, expr, await_promise=False):
        params = {"expression": expr, "returnByValue": True}
        if await_promise:
            params["awaitPromise"] = True
        r = self.send("Runtime.evaluate", params)
        if r and "result" in r:
            return r["result"].get("result", {}).get("value")
        return None

def init_db():
    db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
    os.makedirs(db_dir, exist_ok=True)
    db = os.path.join(db_dir, 'applications.db')
    conn = sqlite3.connect(db)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT, company TEXT, position TEXT, salary TEXT,
        apply_date TEXT DEFAULT (date('now')),
        score INTEGER DEFAULT 0, greeting TEXT, UNIQUE(job_id, company))''')
    cols = [r[1] for r in c.execute("PRAGMA table_info(applications)")]
    if 'greeting' not in cols:
        c.execute("ALTER TABLE applications ADD COLUMN greeting TEXT")
    conn.commit()
    return conn

# ============ 运行时配置（v23 通用化：全部来自 profile.json）============
# 本模块不再硬编码任何行业/城市/薪资默认值。配置在 main() 里通过
# config.load_profile() 载入后写入下面的 _CFG，供过滤与评分函数读取。
# 这样既保留原有函数签名（单测可直接调用），又让配置可被用户覆盖。
_CFG = {
    'apply_outsourcing': True,
    'blacklist': [],
    'outsource_companies': [],
    'negative_keywords': [],
    'exclude_keywords': [],
    'score': {'base': 45, 'strong_positive': [], 'weak_positive': [], 'negative': []},
}

# 兼容旧环境变量：未提供 profile 时仍可用 BOSS_OUTSOURCE 临时切换。
APPLY_OUTSOURCING = os.environ.get('BOSS_OUTSOURCE', '1').strip() not in ('0', 'false', 'False', 'no')


def configure(profile):
    """把 profile.json 的内容写入运行时配置。

    在 main() 载入 profile 后调用一次；单元测试也可直接调用注入自定义配置。
    """
    _CFG['apply_outsourcing'] = bool(profile.get('apply_outsourcing', True))
    _CFG['blacklist'] = list(profile.get('blacklist') or [])
    _CFG['outsource_companies'] = list(profile.get('outsource_companies') or [])
    _CFG['negative_keywords'] = list(profile.get('negative_keywords') or [])
    _CFG['exclude_keywords'] = list(profile.get('exclude_keywords') or [])
    sc = profile.get('score') or {}
    _CFG['score'] = {
        'base': int(sc.get('base', 45)),
        'strong_positive': [str(x).lower() for x in (sc.get('strong_positive') or [])],
        'weak_positive': [str(x).lower() for x in (sc.get('weak_positive') or [])],
        'negative': [str(x).lower() for x in (sc.get('negative') or [])],
    }
    global APPLY_OUTSOURCING
    APPLY_OUTSOURCING = _CFG['apply_outsourcing']
    return _CFG


def is_blacklisted(co):
    """永久黑名单：无论外包是否放宽都不投。"""
    if not co: return False
    blacklist = _CFG.get('blacklist') or []
    if any(b in co for b in blacklist): return True
    if not _CFG.get('apply_outsourcing', True):
        if any(b in co for b in (_CFG.get('outsource_companies') or [])): return True
    return False

def is_headhunter(co, po=''):
    return any(k in co+po for k in ['猎头','猎头顾问','人才经纪人','招聘顾问','HRBP','人力资源','招聘经理','招聘主管','招聘专员','人才服务','招聘'])

def is_internship(po, sal='', tags=None):
    text = (po or '') + (sal or '')
    # v22.1 补漏：0910 实投发现"大数据开发工程师-27届"(字节)/"27秋招数据研发工程师"(滴滴)
    # 混进来了 —— 接口 jobLabels 不含校招标签，而职位名里的"27届/秋招"没被旧词表覆盖。
    # 补入 届/秋招/春招/提前批/管培 等校招特征词。
    if any(k in text for k in ['实习','无经验','接受无经验','应届','可转正','校招','在校','在校生','在读','大四','研二','研三','日结','兼职','小时工',
                               '秋招','春招','提前批','管培','届']):
        return True
    if any(u in (sal or '') for u in ['元/天','元/小时','元/时','/天','/小时','/周']):
        return True
    if tags:
        for t in tags:
            if any(k in (t or '') for k in ['实习','无经验','接受无经验','应届','可转正','校招','在校','在校生','在读','兼职']):
                return True
            if any(u in (t or '') for u in ['元/天','元/小时','/天']):
                return True
    return False

OUTSOURCE_WORDS = ['外包','驻场','外派','派遣','劳务','人力','人力资源服务','技术服务外包','it外包','软件外包','众包']
OUTSOURCE_NEGATE_WORDS = ['非外包','不外包','非驻场','直签','正式编制','正式员工','自研']
ONSITE_WORDS = ['现场面试','线下面试']

def is_onsite_interview(po='', tags=None):
    if any(k in (po or '') for k in ONSITE_WORDS):
        return True
    if tags:
        for t in tags:
            if any(k in (t or '') for k in ONSITE_WORDS):
                return True
    return False

def is_outsource(co, po='', tags=None):
    # 用户配置的外包/人力服务商名单也算外包（中软/软通/法本这类名字里没有"外包"二字）
    if co and any(b in co for b in (_CFG.get('outsource_companies') or [])):
        return True
    text = (co or '') + (po or '')
    if any(n in text for n in OUTSOURCE_NEGATE_WORDS):
        return False
    if any(k in text for k in OUTSOURCE_WORDS):
        return True
    if tags:
        for t in tags:
            if any(n in t for n in OUTSOURCE_NEGATE_WORDS):
                return False
            tl = t.strip()
            if any(k in tl for k in OUTSOURCE_WORDS):
                return True
    return False

def already_applied(conn, jid, co):
    c = conn.cursor()
    ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    c.execute("SELECT 1 FROM applications WHERE job_id=? AND company=? AND apply_date>?",(jid,co,ago))
    return c.fetchone() is not None

def record(conn, jid, co, pos, sal, score=0, greeting=''):
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO applications(job_id,company,position,salary,apply_date,score,greeting) VALUES(?,?,?,?,?,?,?)",
              (jid,co,pos,sal,datetime.now().strftime('%Y-%m-%d'),score,greeting))
    conn.commit()

def parse_salary(s):
    """返回 (下限, 上限)，单位 K；解析不出返回 None。

    v22.2.9 修复：部分岗位按月薪绝对值写（如"22000-40000元"），旧逻辑把
    22000 当成 22000K，导致这类正常岗位被 HIGH(min=22000K) 误拒。
    现按数量级判单位：数值 > 1000 视为"元"，统一除以 1000 转成 K。
    （K 写法一般落在 1~200 之间，且日薪岗会被 is_internship 的"元/天"提前拦掉。）
    """
    if not s: return None
    nums = [int(x) for x in re.findall(r'(\d+)', s)]
    if not nums: return None
    lo = nums[0]
    hi = nums[1] if len(nums) > 1 else nums[0]
    if lo > 1000 or hi > 1000:
        lo, hi = round(lo / 1000), round(hi / 1000)
    return (lo, hi)

def score_job(pos, sal, company=''):
    """按 profile 的评分词表打分。

    v23 通用化：词表全部来自 profile.json 的 score 字段，本函数不再内置任何
    行业词。默认语义（与 v22.2 一致）：
      - base 基础分（默认 45，低于阈值 50 → 零匹配岗位出局）
      - strong_positive 命中任一 +15（强匹配，对口岗位靠它过线）
      - weak_positive 每命中一个 +3
      - negative 每命中一个 -10
    词表在 configure() 里已统一转小写。
    """
    sc = _CFG.get('score') or {}
    score = int(sc.get('base', 45))
    text = (pos or '') + ' ' + (sal or '') + ' ' + (company or '')
    text_lower = text.lower()

    strong_positive = sc.get('strong_positive') or []
    weak_positive = sc.get('weak_positive') or []
    negative = list(sc.get('negative') or [])
    # 外包不放宽时，外包相关词按负向处理
    if not _CFG.get('apply_outsourcing', True):
        negative = ['外包', '驻场', '派遣', '劳务'] + negative

    for kw in strong_positive:
        if kw in text_lower:
            score += 15
            break
    for kw in weak_positive:
        if kw in text_lower:
            score += 3
    for kw in negative:
        if kw in text_lower:
            score -= 10
    return max(0, min(100, score))

# ============ v22 发现层：joblist 接口 ============

def fetch_joblist(cdp, enc_kw, city_code, page, page_size=30):
    """返回 (jobs, err)
    jobs: [dict] 含 encryptJobId/jobName/brandName/salaryDesc/bossOnline/goldHunter/tags/skills/jobType
    err:  None 正常；'ratelimit' 风控；其它为错误串
    """
    js = f"""
    (async function() {{
        try {{
            var u = '/wapi/zpgeek/search/joblist.json?scene=1&query={enc_kw}&city={city_code}&page={page}&pageSize={page_size}';
            var r = await fetch(u, {{headers: {{'accept': 'application/json'}}, credentials: 'include'}});
            var j = await r.json();
            if (j.code !== 0) return JSON.stringify({{_err: 'code_' + j.code, _msg: j.message || ''}});
            var L = (j.zpData || {{}}).jobList || [];
            var out = [];
            for (var i = 0; i < L.length; i++) {{
                var x = L[i];
                var tags = [];
                try {{ tags = JSON.parse(x.jobLabels || '[]'); }} catch(e) {{}}
                var sk = [];
                try {{ sk = JSON.parse(x.skills || '[]'); }} catch(e) {{}}
                out.push({{
                    jobId: x.encryptJobId || '',
                    position: x.jobName || '',
                    company: x.brandName || '',
                    salary: x.salaryDesc || '',
                    bossOnline: (x.bossOnline === 'true' || x.bossOnline === true),
                    goldHunter: (x.goldHunter === '1' || x.goldHunter === 1),
                    tags: tags,
                    skills: sk,
                    jobType: String(x.jobType || ''),
                    proxyJob: String(x.proxyJob || ''),
                    brandIndustry: x.brandIndustry || '',
                    brandScale: x.brandScaleName || '',
                    area: (x.areaDistrict || '') + (x.businessDistrict || '')
                }});
            }}
            return JSON.stringify({{_ok: out}});
        }} catch(e) {{ return JSON.stringify({{_err: 'exception', _msg: String(e)}}); }}
    }})()
    """
    val = cdp.eval(js, await_promise=True)
    if not val:
        return [], 'empty_response'
    try:
        d = json.loads(val)
    except Exception:
        return [], 'bad_json'
    if '_err' in d:
        return [], d['_err'] + ':' + str(d.get('_msg', ''))[:60]
    return d.get('_ok', []), None

def iter_collect(cdp, keywords, city_code, max_pages):
    """逐词采集岗位，每采完一个词就 yield (关键词, 该词新增岗位列表)。

    v22.2.7 边采边投（0911 用户指令）：
      原先是"12 个词全采完 -> 统一排序 -> 统一投递"，导致
        ① 前 12 分钟一个都投不出去，进度完全不可见
        ② 中途被风控打断就整轮白跑（0911 实测发生过一次）
      改为生成器：调用方每拿到一个词就立刻过滤+投递，采完即投、投完再采。
      yield 之后的拟人动作（详情页浏览、批次停顿）在调用方投完该词后执行。

    v22.1 关键修正（0910 实测）：
      页面停留在 /job_detail/ 详情页时调用 joblist 搜索接口，BOSS 返回
      code:37「您的环境存在异常」。原因不是"调接口"本身，而是调用上下文
      与接口语义不符（搜索接口却从详情页发出）。
      修正：每个关键词先"真实导航"到该词的搜索页并等页面加载完，再从该
      页上下文调接口 —— 与 v21 一直好用的请求模式完全一致。

    v22.2.5 拟人化：
      - 每词翻页数随机 2~max_pages（真人不会每个词都翻到底）
      - 翻页/导航间隔用 human_delay 长尾分布，不再等距
      - 导航后在页面模拟滚动；词间约 40% 概率点开一个岗位详情页停留
      - 每 HUMAN_BATCH 个词插入一次 45~90 秒长停顿

    v22.2.6 按 main() 给定的优先级顺序采集（数据开发 > 数据仓库 > ETL > BI > 其余）。
    """
    seen = set()
    order = list(keywords)
    total_kw = len(order)
    print(f"  采集顺序: {' / '.join(order)}")
    for idx, kw in enumerate(order, 1):
        enc = urllib.parse.quote(kw)
        search_url = build_search_url(kw, city_code)
        cdp.eval(f"window.location.href='{search_url}'")
        time.sleep(random.uniform(4.5, 9.0))
        human_scroll(cdp)
        # 等搜索页真正渲染出卡片，确认页面就位再调接口
        for _w in range(5):
            n = cdp.eval("document.querySelectorAll('.job-card-box').length")
            if n and int(n) > 0:
                break
            time.sleep(1.5)

        # 真人不会每个词都翻到底：2~max_pages 随机
        page_limit = max_pages if max_pages <= 2 else random.randint(2, max_pages)
        got_kw, page, kw_jobs = 0, 1, []
        while page <= page_limit:
            jobs, err = fetch_joblist(cdp, enc, city_code, page)
            if err:
                if err.startswith('code_37') or 'security' in err.lower():
                    raise RiskControlError(f"风控触发：{err}")
                print(f"  page {page}: 接口异常 {err} -> 停该词")
                break
            if not jobs:
                break
            new = 0
            for j in jobs:
                k = f"{j['jobId']}_{j['company']}"
                if k in seen or not j['jobId']:
                    continue
                seen.add(k)
                j['_kw'] = kw
                kw_jobs.append(j)   # v22.2.7: 只累积本词，交给调用方即时投递
                new += 1
            got_kw += new
            print(f"  page {page}: {len(jobs)} jobs, +{new} new (该词累计 {got_kw})")
            if new == 0:
                break
            page += 1
            if page <= page_limit:
                time.sleep(human_delay())
        print(f"  关键词 [{kw}] 采集 {got_kw} 个（翻 {page - 1} 页）")

        # v22.2.7: 本词采完立刻交给调用方过滤+投递；下面的拟人动作
        # 会等调用方投完这个词之后才继续执行
        yield kw, kw_jobs

        # 拟人：看完一批岗位，随机点开一个详情页停留一下再退回列表
        if kw_jobs and idx < total_kw and random.random() < 0.4:
            pick = random.choice(kw_jobs[:8])
            stay = random.uniform(4.0, 9.0)
            cdp.eval(f"window.location.href='https://www.zhipin.com/job_detail/{pick['jobId']}.html'")
            print(f"    [拟人] 点开详情：{(pick['position'] or '')[:18]} @ "
                  f"{(pick['company'] or '')[:12]} 停留 {stay:.0f}s")
            time.sleep(stay)
            cdp.eval(f"window.location.href='{search_url}'")
            time.sleep(random.uniform(3.0, 6.0))
            human_scroll(cdp)

        # 拟人：每 HUMAN_BATCH 个词歇一口气
        if idx % HUMAN_BATCH == 0 and idx < total_kw:
            pause = random.uniform(45.0, 90.0)
            print(f"    [拟人] 批次间停顿 {pause:.0f}s ...")
            time.sleep(pause)


def collect_all(cdp, keywords, city_code, max_pages):
    """一次性收齐所有岗位 —— 保留旧接口，单元测试与外部调用仍可用。

    v22.2.7: 主流程已改用 iter_collect 边采边投，此函数仅作兼容包装。
    """
    all_jobs = []
    for _kw, _jobs in iter_collect(cdp, keywords, city_code, max_pages):
        all_jobs.extend(_jobs)
    return all_jobs


def iter_jobs(cdp, keywords, city_code, max_pages, risk_holder=None):
    """逐词采集 + 词内排序，逐个产出岗位 —— 主流程边采边投用。

    v22.2.7: 每采完一个关键词就立刻排序并产出它的岗位，主流程的投递循环
    边消费边投递，实现"采完即投、投完再采下一个词"。
    关键词优先级由 keywords 列表顺序保证；词内保持"非外包优先"。

    risk_holder: 可选 dict。采集中途若触发风控，把异常对象放进去而不直接
    抛出，让调用方的 for 循环自然结束、已投出的记录得以保留，循环后再统一处理。
    """
    try:
        for _kw, kw_jobs in iter_collect(cdp, keywords, city_code, max_pages):
            if not kw_jobs:
                continue
            kw_jobs.sort(key=lambda _j: 1 if is_outsource(
                decode_font(_j['company']), decode_font(_j['position']), _j['tags']) else 0)
            print(f"\n  --- 【{_kw}】候选 {len(kw_jobs)} 个（词内非外包优先）---")
            for _j in kw_jobs:
                yield _j
    except RiskControlError as exc:
        if risk_holder is not None:
            risk_holder['exc'] = exc
        else:
            raise

# ============ v22 投递层：详情页直投 ============

def apply_via_detail(cdp, job, greeting=''):
    """直接打开职位详情页投递。返回 (status, detail)

    greeting: profile.json 里的自定义招呼语。为空时只用 BOSS 默认招呼语
              （点「立即沟通」后直接发送）；非空时在弹窗的输入框里填入该文本。
    """
    jid = job['jobId']
    url = f"https://www.zhipin.com/job_detail/{jid}.html"
    cdp.eval(f"window.location.href='{url}'")
    time.sleep(random.uniform(2.5, 4.0))

    # 1. 页面是否可用
    body_len = cdp.eval("document.body ? document.body.innerText.length : 0")
    if not body_len or int(body_len) < 200:
        time.sleep(3)
        body_len = cdp.eval("document.body ? document.body.innerText.length : 0") or 0
        if int(body_len) < 200:
            return 'PAGE_EMPTY', ''

    # 2. 标题校验（防串号）
    pos_page = (cdp.eval("(document.querySelector('.job-name')||document.querySelector('h1')||{}).textContent||''") or '').strip()
    if pos_page and job['position']:
        p = job['position'][:6]
        if p not in pos_page:
            return 'MISMATCH', f'page={pos_page[:20]}'
    # 职位已关闭
    if any(k in pos_page for k in ['职位已关闭', '不存在', '已下线']):
        return 'CLOSED', ''

    # 3. 点"立即沟通"
    res = cdp.eval("""(function() {
        var a = document.querySelector('a.btn-startchat') || document.querySelector('.btn-startchat');
        if (!a) return 'nf';
        var t = (a.textContent || '').trim();
        if (a.className.indexOf('is-disabled') >= 0) return 'disabled';
        if (t.indexOf('继续') >= 0) return 'contacted';
        a.click();
        return 'ok';
    })()""")
    if res in ('nf', 'disabled'):
        return 'NO_BUTTON', str(res)
    if res == 'contacted':
        return 'ALREADY', ''

    # 4. 等弹窗 / 已发送
    time.sleep(random.uniform(1.8, 3.0))
    dlg = cdp.eval("""(function(){
        var d = document.querySelector('.greet-boss-dialog') || document.querySelector('.dialog-container') || document.querySelector('.dialog-wrap');
        return d ? d.textContent.substring(0, 200) : '';
    })()""") or ''

    # 4.5 v23: 自定义招呼语 —— profile.greeting 非空时填入输入框再发送。
    if greeting:
        filled = cdp.eval("""(function(){
            var t = %s;
            var box = document.querySelector('.greet-boss-dialog textarea')
                   || document.querySelector('.dialog-container textarea')
                   || document.querySelector('textarea.input-area')
                   || document.querySelector('.chat-input');
            if (!box) return 'no_box';
            if (box.tagName === 'TEXTAREA' || box.tagName === 'INPUT') {
                box.focus();
                box.value = t;
            } else {
                box.focus();
                box.textContent = t;
            }
            box.dispatchEvent(new Event('input', {bubbles: true}));
            box.dispatchEvent(new Event('change', {bubbles: true}));
            return 'filled';
        })()""" % json.dumps(greeting))
        if filled == 'filled':
            time.sleep(random.uniform(0.5, 1.2))
            cdp.eval("""(function(){
                var btns = document.querySelectorAll('.greet-boss-dialog .btn-sure, .greet-boss-dialog .sure-btn, .dialog-container .btn-sure, .dialog-container .sure-btn');
                for (var i=0;i<btns.length;i++){
                    var t = (btns[i].textContent||'').trim();
                    if (t === '发送' || t === '发送消息' || t === '确定') { btns[i].click(); return 'ok'; }
                }
                return 'no';
            })()""")
            time.sleep(random.uniform(1.0, 2.0))

    if dlg and ('已向' in dlg or '发送' in dlg or 'BOSS' in dlg):
        cdp.eval("""(function(){
            var btns = document.querySelectorAll('.sure-btn, .btn-sure, .dialog-container .btn');
            for (var i=0;i<btns.length;i++){
                var t = (btns[i].textContent||'').trim();
                if (t === '继续沟通' || t === '确定' || t === '知道了') { btns[i].click(); return 'ok'; }
            }
            return 'no';
        })()""")
        time.sleep(1)
        return 'OK', dlg[:40].replace('\n', ' ')
    # 没弹窗：可能直接进了聊天或已沟通
    return 'OK_NODLG', dlg[:40].replace('\n', ' ')

def preflight(cdp, city_code, probe_keyword=None):
    """开跑前健康检查（v22.1 修正）。

    曾用前端 cookie 判断登录 —— 错误：BOSS 的登录凭证是 HttpOnly cookie，
    JS 读不到，该检查会误报"未登录"并把正常跑批全拦下来。

    改为**功能探测**：拿探针词page1，看三件事
      1. code 是否为 0（非 0 = 风控/异常）
      2. 是否返回岗位
      3. 岗位是否带 salaryDesc
    风控冷却期 BOSS 会降级返回（只给 15 条且 salaryDesc 全空），
    此时开跑必然大批 NO_SALARY，直接终止等待恢复。
    返回 (ok: bool, msg: str)

    v23: 探针词由调用方传入（默认取 profile 的第一个关键词），不再写死行业词。
    """
    enc = urllib.parse.quote(probe_keyword or '')
    jobs, err = fetch_joblist(cdp, enc, city_code, 1)
    if err:
        return False, f"接口异常 {err}"
    if not jobs:
        return False, "接口返回 0 岗位（可能风控或页面异常）"
    with_sal = sum(1 for j in jobs if j.get('salary'))
    if with_sal == 0:
        return False, (f"返回 {len(jobs)} 条但薪资全空 —— BOSS 风控降级中，"
                       f"此时开跑会全被 NO_SALARY 拦掉，建议稍后重试")
    return True, f"正常（{len(jobs)} 条，带薪资 {with_sal} 条）"

def main():
    import sys as _sys
    DRY = '--dry' in _sys.argv
    print("=" * 60)
    print("BOSS直聘 Auto Apply v23 (通用版: 接口发现+详情页直投, 配置来自 profile.json)" + ("  [DRY-RUN 只筛选不投递]" if DRY else ""))
    print("=" * 60)
    t0 = datetime.now()

    # v23 通用化：所有个人化配置（关键词/城市/薪资/评分词表/黑名单）来自
    # profile.json。缺失或非法时 config.load_profile 会抛出带引导话术的
    # ProfileError —— 直接打印给用户看，不静默套用别的行业默认值。
    #
    # 注意顺序：配置检查必须排在连接 Chrome CDP **之前**。否则首次使用的用户
    # 若还没启动 CDP Chrome，会先撞上 get_ws_url() 的连接异常，根本看不到
    # 首次引导话术 —— 那正是本 skill 最需要传达信息的一刻。
    try:
        prof = load_profile()
    except ProfileError as exc:
        print("\n" + "!" * 60)
        print("!! 未找到可用的个人配置 —— 本轮不运行")
        print("!" * 60)
        print(f"{exc}")
        print("!" * 60)
        return

    configure(prof)

    keywords = prof['keywords']
    city_code = prof['city_code']
    max_pages = prof['max_pages']
    max_apply = prof['max_apply']
    DAILY_LIMIT = prof['daily_limit']
    salary_floor_k = prof['salary_floor_k']
    min_salary_k = prof['salary_min_k']
    max_salary_k = prof['salary_max_k']
    score_threshold = prof['score_threshold']

    print(f"配置来源: {profile_path()}")
    print(f"城市: {prof['city']} ({city_code}) | 关键词 {len(keywords)} 个 | "
          f"薪资 {min_salary_k + 1}~{max_salary_k}K | 单轮上限 {max_apply} | 阈值 {score_threshold}")

    # 配置就绪后才连接 CDP Chrome
    conn = init_db()
    try:
        ws_url = get_ws_url()
        cdp = CDP(ws_url)
        title = cdp.eval('document.title')
    except Exception as exc:
        # 最常见的原因就是没启动隔离 Chrome。给一条能直接照做的提示，
        # 不要让用户对着一屏 Python traceback 猜。
        print("\n" + "!" * 60)
        print("!! 连不上 Chrome 调试端口 127.0.0.1:9223 —— 本轮不运行")
        print("!" * 60)
        print(f"!! 原因：{type(exc).__name__}: {exc}")
        print("!!")
        print("!! 处理：先在另一个终端启动隔离 Chrome（保持它开着）：")
        print("!!     python scripts/start_cdp_v2.py")
        print("!! 首次使用还需在该窗口里登录 BOSS 直聘：")
        print("!!     python tools/wait_login.py --timeout 1800")
        print("!! 然后重跑本命令。")
        print("!" * 60)
        conn.close()
        return
    print(f"Connected: {title}")

    _c = conn.cursor()
    _c.execute("SELECT COUNT(*) FROM applications WHERE apply_date=date('now','localtime')")
    _today_done = _c.fetchone()[0]
    _remain_today = DAILY_LIMIT - _today_done
    if _remain_today <= 0:
        print(f"\n!! 今日已投 {_today_done} 个，已达每日上限 {DAILY_LIMIT} —— 本轮不投递。")
        conn.close()
        return
    if _remain_today < max_apply:
        print(f"\n今日已投 {_today_done} 个，本轮上限收敛为 {_remain_today} 个"
              f"（每日上限 {DAILY_LIMIT}）")
        max_apply = _remain_today

    # 搜索接口必须从 zhipin.com 页面上下文发出，先导航再做健康检查。
    ensure_zhipin_page(cdp, city_code=city_code, keyword=keywords[0])

    # ---- 开跑前健康检查：接口是否正常返回带薪资的岗位 ----
    ok, msg = preflight(cdp, city_code=city_code, probe_keyword=keywords[0])
    if not ok:
        print("\n" + "!" * 60)
        print("!! 接口健康检查未通过 —— 已终止，避免白跑一轮")
        print(f"!! {msg}")
        print("!! 处理：等待几分钟让风控冷却，或确认 Chrome 页面正常后重跑。")
        print("!" * 60)
        return
    print(f"接口健康检查: {msg}")

    # ---------- 边采边投（v22.2.7，0911 用户指令）----------
    # 原设计是"12 个词全采完 -> 统一排序 -> 统一投递"，有两个硬伤：
    #   ① 前 12 分钟一个都投不出去，进度完全不可见
    #   ② 中途被风控打断就整轮白跑（0911 实测发生过一次）
    # 现改为：采完一个关键词就立刻投它的岗位，投完再采下一个词。
    # 关键词优先级由 keywords 列表顺序保证（数据开发 > 数据仓库 > ETL > BI > 其余）。
    print("\n[采集+投递] 边采边投：采完一个关键词即投递该词的岗位 ...")
    _risk = {}
    jobs = iter_jobs(cdp, keywords, city_code, max_pages, risk_holder=_risk)

    applied = 0
    stats = {}
    # 熔断：连续 N 次非成功投递说明大概率触发风控/页面异常，立即停手，
    # 不要继续硬刷（0910 用户明确要求防封号）。
    consec_fail = 0
    MAX_CONSEC_FAIL = 5
    for job in jobs:
        if applied >= max_apply:
            print("  (达到单轮上限)")
            break
        if consec_fail >= MAX_CONSEC_FAIL:
            print(f"\n  !! 连续 {consec_fail} 次投递失败 -> 熔断停止（疑似风控或页面异常）")
            break

        co = decode_font(job['company'])
        pos = decode_font(job['position'])
        sal = job['salary']

        def rej(r):
            stats[r] = stats.get(r, 0) + 1
            print(f"  - [{job['_kw']}] {pos[:32]} | {co[:20]} | {sal} -> {r}")

        if not pos or not co:
            rej('EMPTY'); continue
        if co == 'BOSS直聘':
            rej('PLACEHOLDER'); continue
        if job['goldHunter']:
            rej('HEADHUNTER'); continue
        if is_blacklisted(co):
            rej('BLACK'); continue
        if is_headhunter(co, pos):
            rej('HEADHUNTER_TEXT'); continue
        if is_internship(pos, sal, job['tags']):
            rej('INTERN'); continue
        if is_onsite_interview(pos, job['tags']):
            rej('ONSITE'); continue
        # 外包不再拦截，只做排序优先级（见阶段1.5）。
        # BOSS_OUTSOURCE=0 时恢复"外包直接跳过"的旧行为。
        if not APPLY_OUTSOURCING and is_outsource(co, pos, job['tags']):
            rej('OUTSOURCE'); continue

        si = parse_salary(sal)
        # v22.2.13: 上沿必须 > min_salary_k（现值 17 → 要求上沿 ≥18K）。
        if si and si[1] <= min_salary_k:
            rej(f'LOW(max={si[1]}K)'); continue
        # v22.2.12: 下限门槛默认关闭（salary_floor_k = 0 时不启用）；
        #   将来需要"起薪不得低于 N K"时把 salary_floor_k 改回 N 即生效。
        if salary_floor_k and si and si[0] < salary_floor_k:
            rej(f'LOWFLOOR(min={si[0]}K)'); continue
        if si and si[0] > max_salary_k:
            rej(f'HIGH(min={si[0]}K)'); continue
        if si is None:
            rej('NO_SALARY'); continue

        if already_applied(conn, job['jobId'], co):
            stats['APPLIED_30D'] = stats.get('APPLIED_30D', 0) + 1
            continue
        # v22.2.2: 恢复 0807 放宽 —— BOSS 不在线不再拦截（招呼消息会留存，HR 上线可见），
        # 仅标注 [离线]。v22.2 原行为为下方 rej('OFFLINE') 直接跳过。
        _offline = not job['bossOnline']

        sc = score_job(pos, sal, co)
        if sc < score_threshold:
            rej(f'LOWSCORE({sc})'); continue

        # 终审保险
        if any(k in (pos + sal) for k in ['实习','校招','在校','在读','应届','无经验','兼职','日结','秋招','春招','提前批','管培','届']):
            rej('FIN_INTERN'); continue
        # v23: 以下「用户自定义排除词」与「用户自定义负向词」取代了 v22.2 里
        #      写死的纯 Java / 数据治理 / 销售话术词表 —— 那些词只对数据岗有意义。
        if _CFG.get('exclude_keywords') and any(
                w in pos for w in _CFG['exclude_keywords']):
            rej('EXCLUDE_KW'); continue
        if _CFG.get('negative_keywords') and any(
                w.lower() in pos.lower() for w in _CFG['negative_keywords']):
            rej('NEGATIVE_KW'); continue

        # 投递
        print(f"  > [{job['_kw']}]{'[离线]' if _offline else ''} {pos[:34]} | {co[:20]} | {sal} | 分{sc}", end=' ', flush=True)
        if DRY:
            applied += 1
            stats['DRY_PASS'] = stats.get('DRY_PASS', 0) + 1
            print(f"-> 可投 ({applied})")
            continue
        status, info = apply_via_detail(cdp, job, greeting=prof.get('greeting') or '')
        if status in ('OK', 'OK_NODLG'):
            record(conn, job['jobId'], co, pos, sal, sc, prof.get('greeting') or '默认招呼语')
            applied += 1
            consec_fail = 0
            print(f"-> {status} ✔ ({applied}/{max_apply}) {info}")
            # 防封号：投递间隔拉长到 3~5.5s，接近真人逐个查看职位后沟通的节奏
            time.sleep(human_delay(fast=(3.0, 5.5), slow=(8.0, 14.0),
                                   away=(20.0, 35.0), p_fast=0.85, p_slow=0.97))
        elif status == 'ALREADY':
            record(conn, job['jobId'], co, pos, sal, sc, '已沟通过')
            stats['ALREADY'] = stats.get('ALREADY', 0) + 1
            consec_fail = 0
            print("-> ALREADY(已沟通过)")
            time.sleep(random.uniform(1.0, 2.0))
        else:
            stats[status] = stats.get(status, 0) + 1
            consec_fail += 1
            print(f"-> {status} {info} (连续失败 {consec_fail}/{MAX_CONSEC_FAIL})")
            time.sleep(random.uniform(1.0, 2.0))

    if _risk.get('exc'):
        print("\n" + "!" * 60)
        print(f"!! {_risk['exc']}")
        print("!! 已立即终止整轮；本轮不重试、不换词、不继续投递。")
        print(f"!! 本轮已投出 {applied} 个，记录已落库不会丢失。")
        print("!" * 60)

    dt = (datetime.now() - t0).total_seconds()
    print("\n" + "=" * 60)
    print(f"完成！本次投递 {applied} 个，耗时 {int(dt)}s")
    print("\n拒绝/跳过统计：")
    for k, v in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {k:16s} {v}")
    print("=" * 60)
    conn.close()

if __name__ == '__main__':
    main()
