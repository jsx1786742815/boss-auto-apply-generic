# -*- coding: utf-8 -*-
"""不依赖第三方库的 CDP 页面选择与搜索页导航工具。

v23 通用化：不再内置默认城市/关键词 —— 这两项因用户而异，全部由
profile.json 提供（见 scripts/config.py）。这里只保留纯函数式的拼接。
"""
import time
import urllib.parse


def build_search_url(keyword, city_code):
    """拼 BOSS 搜索页 URL。keyword 与 city_code 均为必填（由 profile 提供）。"""
    encoded_keyword = urllib.parse.quote(keyword or "")
    return (
        "https://www.zhipin.com/web/geek/jobs"
        f"?query={encoded_keyword}&city={city_code}&industry=&position="
    )


def pick_cdp_page(pages):
    if not pages:
        return None
    for page in pages:
        if page.get("type") == "page" and "zhipin.com" in str(page.get("url") or ""):
            return page
    for page in pages:
        if page.get("type") == "page":
            return page
    return pages[0]


def ensure_zhipin_page(
    cdp,
    city_code,
    keyword,
    wait_seconds=5.0,
    sleep=time.sleep,
):
    """确保 CDP 当前页面位于 BOSS 域名下。

    搜索接口必须从 zhipin.com 页面上下文发出，否则 BOSS 会返回
    code:37「您的环境存在异常」（v22.1 实测确认）。
    """
    current = cdp.eval("window.location.href") or ""
    if "zhipin.com" in current:
        return current

    target = build_search_url(keyword, city_code)
    cdp.eval(f"window.location.href='{target}'")
    sleep(wait_seconds)
    return target
