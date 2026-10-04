# -*- coding: utf-8 -*-
"""Enshrouded wiki.gg 武器数据抓取管道
用法: python scrape_weapons.py
输出: ../src/data/weapons.json
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://enshrouded.wiki.gg/api.php"
UA = "EmberDB-scraper/1.0 (site data pipeline)"

SUBCATS = [
    "Daggers", "One-handed Axes", "One-handed Clubs", "One-handed Swords",
    "Two-handed Axes", "Two-handed Clubs", "Two-handed Greatswords",
    "Two-handed Hammers", "Staves", "Wands", "Bows", "Throwing Weapons",
]


def api_get(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  重试({attempt+1}): {e}", file=sys.stderr)
            time.sleep(3)


def list_category(cat):
    """返回分类下所有 page 标题"""
    titles = []
    cont = None
    while True:
        params = {
            "action": "query", "list": "categorymembers",
            "cmtitle": f"Category:{cat}", "cmlimit": "500",
            "cmtype": "page", "format": "json",
        }
        if cont:
            params.update(cont)
        d = api_get(params)
        titles += [m["title"] for m in d["query"]["categorymembers"]]
        cont = d.get("continue")
        if not cont:
            return titles


def fetch_wikitexts(titles):
    """按批获取 wikitext, 返回 {title: wikitext}"""
    out = {}
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        d = api_get({
            "action": "query", "prop": "revisions",
            "rvprop": "content", "rvslots": "main",
            "titles": "|".join(batch), "format": "json",
        })
        for page in d["query"]["pages"].values():
            if "revisions" in page:
                out[page["title"]] = page["revisions"][0]["slots"]["main"]["*"]
            else:
                print(f"  无内容: {page['title']}", file=sys.stderr)
        time.sleep(0.5)  # 礼貌限速
    return out


def parse_template(wikitext, name):
    """解析 {{Name|key=value|...}} 模板参数为 dict"""
    m = re.search(r"\{\{\s*" + re.escape(name) + r"\s*\|(.*?)\}\}", wikitext, re.S)
    if not m:
        return {}
    body = m.group(1)
    params = {}
    depth = 0
    cur = ""
    parts = []
    for ch in body:
        if ch == "{" or ch == "[":
            depth += 1
        elif ch == "}" or ch == "]":
            depth -= 1
        if ch == "|" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.strip().lower()] = v.strip()
        elif p.strip():
            params.setdefault("_positional", []).append(p.strip())
    return params


def clean(s):
    """去掉 wiki 标记：链接 [[a|b]] -> b, ''' -> '', <br> -> ', '"""
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"'{2,}", "", s)
    s = re.sub(r"<br\s*/?>", ", ", s, flags=re.I)
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    # 兜底：清掉被截断的模板尾巴与孤立括号
    s = re.sub(r"\{\{[^{}]*$", "", s)
    s = s.replace("}}", "").replace("{{", "")
    return s.strip()


def slugify(title):
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def main():
    all_titles = {}
    for cat in SUBCATS:
        titles = list_category(cat)
        label = cat
        for t in titles:
            all_titles.setdefault(t, label)
        print(f"{cat}: {len(titles)} 个页面")
    titles = sorted(all_titles)
    print(f"共 {len(titles)} 个武器页面，开始抓取 wikitext...")

    texts = fetch_wikitexts(titles)
    weapons = []
    for t in titles:
        wt = texts.get(t, "")
        infobox = parse_template(wt, "Item Infobox")
        stats = parse_template(wt, "Weapon Stats")
        if not stats and not infobox:
            continue
        cat_label = all_titles[t]
        w = {
            "name": t,
            "slug": slugify(t),
            "type": clean(stats.get("weapontype") or infobox.get("type") or cat_label.rstrip("s")),
            "category": cat_label,
            "level": stats.get("level", ""),
            "attackSpeed": stats.get("attackspeed", ""),
            "perks": [clean(p) for p in stats.get("perks", "").split(",") if clean(p)],
            "source": [clean(s) for s in re.split(r"[;,]", stats.get("source", "")) if clean(s)],
            "description": clean(infobox.get("description", "")),
            "image": infobox.get("images", "").split(",")[0].strip(),
        }
        weapons.append(w)

    weapons.sort(key=lambda w: (w["category"], w["name"].lower()))
    import os
    out_path = os.path.join(os.path.dirname(__file__), "..", "src", "data", "weapons.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(weapons, f, ensure_ascii=False, indent=2)
    print(f"写入 {len(weapons)} 条武器数据 -> {out_path}")


if __name__ == "__main__":
    main()
