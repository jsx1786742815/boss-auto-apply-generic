# -*- coding: utf-8 -*-
"""profile.json 配置加载层 —— 让本 skill 适用于任意行业/城市/薪资偏好。

设计原则：
  1. 所有「个人化」的东西都进 profile.json，Python 代码里不再有硬编码默认行业。
  2. 缺少 profile 时**不静默使用数据行业默认值**，而是给出明确的引导提示 ——
     否则产品/设计岗用户会拿到数据岗词表，岗位全被 LOWSCORE 拦光却不知道为什么。
  3. 提供 built-in 行业模板（templates/）降低填写门槛。
"""
import json
import os

# ---------------------------------------------------------------------------
# 城市名 -> BOSS 城市编码
# 只需要覆盖常用城市；未收录的城市可让用户直接填 9 位编码，
# 或从 references/city_codes.md 里查后填入 profile。
# ---------------------------------------------------------------------------
CITY_CODES = {
    # 一线
    '北京': '101010100', '上海': '101020100', '广州': '101280100', '深圳': '101280600',
    # 新一线
    '杭州': '101210100', '成都': '101270100', '武汉': '101200100', '南京': '101190100',
    '西安': '101110100', '苏州': '101190400', '天津': '101030100', '长沙': '101250100',
    '郑州': '101180100', '重庆': '101040100', '青岛': '101120200', '东莞': '101281600',
    '宁波': '101210400', '佛山': '101280800', '合肥': '101220100', '沈阳': '101070100',
    # 其他常用
    '无锡': '101190200', '厦门': '101230200', '福州': '101230100', '济南': '101120100',
    '大连': '101070200', '哈尔滨': '101050100', '长春': '101060100', '石家庄': '101090100',
    '太原': '101100100', '南昌': '101240100', '贵阳': '101260100', '昆明': '101290100',
    '南宁': '101300100', '兰州': '101160100', '珠海': '101280700', '中山': '101281700',
    '惠州': '101280300', '温州': '101210700', '嘉兴': '101210300', '泉州': '101230400',
    '徐州': '101190800', '常州': '101191100', '烟台': '101120500', '潍坊': '101120600',
    '绍兴': '101210500', '台州': '101210600', '金华': '101210900', '保定': '101090200',
}

# 各字段默认值。注意：keywords / 词表类字段**故意不设行业默认**，
# 必须由用户 profile 提供（templates 里有可直接套用的行业模板）。
DEFAULTS = {
    'city': '北京',
    'max_pages': 3,
    'max_apply': 50,
    'daily_limit': 100,
    'score_threshold': 50,
    'salary_min_k': 14,       # 区间上沿须 > 该值
    'salary_max_k': 35,       # 区间下沿高于该值则跳过
    'salary_floor_k': 0,      # 0 = 不启用「起薪不得低于 N K」
    'apply_outsourcing': True,
    'allow_offline_boss': True,
    'greeting': '',           # 空 = 只用 BOSS 默认招呼语
}

# 最少必须提供的字段 —— 缺失即报错并指引用户运行引导流程
REQUIRED = ('keywords', 'score')

PROFILE_ENV = 'BOSS_PROFILE'
PROFILE_NAME = 'profile.json'


class ProfileError(RuntimeError):
    """profile.json 缺失或非法。信息面向最终用户，必须可直接照做。"""


def skill_root():
    """skill 根目录（本文件位于 <root>/scripts/config.py）。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def profile_path():
    """profile.json 路径：优先 $BOSS_PROFILE，其次 skill 根目录。"""
    env = os.environ.get(PROFILE_ENV, '').strip()
    if env:
        return os.path.abspath(env)
    return os.path.join(skill_root(), PROFILE_NAME)


def city_to_code(city):
    """城市名或 9 位编码 -> 编码。无法识别时抛 ProfileError。"""
    if not city:
        raise ProfileError("profile 里的 city 为空。")
    c = str(city).strip()
    if c.isdigit() and len(c) == 9:
        return c
    code = CITY_CODES.get(c)
    if code:
        return code
    # 兼容 "北京市" 这类写法
    if c.endswith('市') and c[:-1] in CITY_CODES:
        return CITY_CODES[c[:-1]]
    raise ProfileError(
        f"无法识别城市「{city}」。请填写常用城市名（如 北京/上海/深圳），"
        f"或直接填 BOSS 的 9 位城市编码；编码见 references/city_codes.md。"
    )


def _as_str_list(value, field):
    if value is None:
        return []
    if not isinstance(value, list):
        raise ProfileError(f"profile 字段「{field}」应为字符串数组，实际是 {type(value).__name__}。")
    out = []
    for item in value:
        if not isinstance(item, str):
            raise ProfileError(f"profile 字段「{field}」的元素必须都是字符串。")
        s = item.strip()
        if s:
            out.append(s)
    return out


def _as_int(value, field, default):
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ProfileError(f"profile 字段「{field}」应为整数，实际是 {value!r}。")


def _as_bool(value, field, default):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ('0', 'false', 'no', 'off', '')
    return bool(value)


def _guide_text(reason):
    return (
        f"{reason}\n"
        f"  这是本 skill 的首次使用引导：请向用户收集以下信息，然后生成\n"
        f"  {profile_path()}\n"
        f"  必填：keywords（搜索关键词，按优先级排序）、score（评分词表）\n"
        f"  选填：city、salary_min_k/salary_max_k、blacklist、negative_keywords\n"
        f"  可参考 templates/ 下的行业模板（数据/产品/设计/运营/测试/前端/销售等），\n"
        f"  以及 references/profile_schema.md 的字段说明。"
    )


def load_profile(path=None):
    """读取并校验 profile.json，返回带默认值补齐的 dict。

    缺失或非法时抛 ProfileError，异常信息即给用户的引导话术。
    """
    p = path or profile_path()
    if not os.path.exists(p):
        raise ProfileError(_guide_text(f"未找到配置文件：{p}"))

    try:
        with open(p, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise ProfileError(_guide_text(f"配置文件不是合法 JSON：{p}（{e}）"))
    except OSError as e:
        raise ProfileError(f"无法读取配置文件 {p}：{e}")

    if not isinstance(raw, dict):
        raise ProfileError(_guide_text(f"配置文件根节点应为 JSON 对象：{p}"))

    prof = dict(DEFAULTS)

    # --- 关键词：按顺序即优先级 ---
    if 'keywords' not in raw:
        raise ProfileError(_guide_text("profile 缺少必填字段「keywords」。"))
    keywords = _as_str_list(raw.get('keywords'), 'keywords')
    if not keywords:
        raise ProfileError(_guide_text("profile 的「keywords」为空，至少需要 1 个搜索关键词。"))
    prof['keywords'] = keywords

    # --- 城市 ---
    city = raw.get('city', DEFAULTS['city'])
    prof['city'] = city
    prof['city_code'] = city_to_code(city)

    # --- 评分词表 ---
    if 'score' not in raw:
        raise ProfileError(_guide_text("profile 缺少必填字段「score」（评分词表）。"))
    score_raw = raw.get('score')
    if not isinstance(score_raw, dict):
        raise ProfileError("profile 字段「score」应为对象，含 strong_positive/weak_positive/negative。")
    prof['score'] = {
        'base': _as_int(score_raw.get('base'), 'score.base', 45),
        'strong_positive': _as_str_list(score_raw.get('strong_positive'), 'score.strong_positive'),
        'weak_positive': _as_str_list(score_raw.get('weak_positive'), 'score.weak_positive'),
        'negative': _as_str_list(score_raw.get('negative'), 'score.negative'),
    }
    if not prof['score']['strong_positive']:
        raise ProfileError(_guide_text(
            "profile 的「score.strong_positive」为空。该词表决定哪些岗位能过评分线，"
            "必须至少包含几个与目标岗位强相关的词（如行业术语/技术栈/职位核心词）。"))

    # --- 数值项 ---
    for key in ('max_pages', 'max_apply', 'daily_limit', 'score_threshold',
                'salary_min_k', 'salary_max_k', 'salary_floor_k'):
        prof[key] = _as_int(raw.get(key), key, DEFAULTS[key])

    if prof['max_apply'] <= 0:
        raise ProfileError("profile 的「max_apply」必须大于 0。")
    if prof['daily_limit'] < prof['max_apply']:
        # 每日上限低于单轮上限会让单轮额度被无意义地截断
        prof['daily_limit'] = prof['max_apply']

    # --- 布尔项 ---
    prof['apply_outsourcing'] = _as_bool(raw.get('apply_outsourcing'),
                                         'apply_outsourcing', DEFAULTS['apply_outsourcing'])
    prof['allow_offline_boss'] = _as_bool(raw.get('allow_offline_boss'),
                                          'allow_offline_boss', DEFAULTS['allow_offline_boss'])

    # --- 列表项（可选）---
    prof['blacklist'] = _as_str_list(raw.get('blacklist'), 'blacklist')
    prof['outsource_companies'] = _as_str_list(raw.get('outsource_companies'), 'outsource_companies')
    prof['negative_keywords'] = _as_str_list(raw.get('negative_keywords'), 'negative_keywords')
    prof['exclude_keywords'] = _as_str_list(raw.get('exclude_keywords'), 'exclude_keywords')

    greeting = raw.get('greeting') or ''
    prof['greeting'] = greeting.strip() if isinstance(greeting, str) else ''

    return prof


def list_templates():
    """返回内置行业模板 {name: 描述}。"""
    tdir = os.path.join(skill_root(), 'templates')
    out = {}
    if not os.path.isdir(tdir):
        return out
    for fn in sorted(os.listdir(tdir)):
        if not fn.endswith('.json'):
            continue
        name = fn[:-5]
        desc = ''
        try:
            with open(os.path.join(tdir, fn), 'r', encoding='utf-8') as f:
                desc = (json.load(f).get('_description') or '')
        except Exception:
            pass
        out[name] = desc
    return out
