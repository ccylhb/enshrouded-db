# -*- coding: utf-8 -*-
"""Enshrouded wiki.gg 护甲数据抓取管道（单件 + 套装）
用法: python scrape_armor.py
输出: ../src/data/armor.json, ../src/data/armor-sets.json
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://enshrouded.wiki.gg/api.php"
UA = "EmberDB-scraper/1.0 (site data pipeline)"

PIECE_CATS = {
    "Melee Armor": "melee",
    "Magic Armor": "magic",
    "Ranged Armor": "ranged",
    "Miscellaneous Armor": "misc",
}


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


# --- wiki 魔术字展开 ---------------------------------------------------------
# 清洗器整段删无名模板，{{PAGENAME}}（条目名）随之消失，正文出现主语缺失残句。
_MAGIC_TITLE = re.compile(r"\{\{\s*(?:SUB|BASE|FULL)?PAGENAME(?:E)?\s*\}\}", re.I)
_MAGIC_GAME = re.compile(r"\{\{\s*(?:Gamename|Game|SITENAME|Sitename)\s*\}\}", re.I)
_MAGIC_DROP = re.compile(
    r"\{\{\s*(?:DISPLAYTITLE|DEFAULTSORT|#(?:expr|var|if|ifeq|ifexist|switch|tag|invoke|time|pos|len|replace|sub|explode|titleparts)[^}]*)\}\}",
    re.I,
)


def expand_magic(wt, title):
    """把 {{PAGENAME}} 换成条目名，丢弃解析器函数等元魔术字。"""
    if not wt:
        return wt
    wt = _MAGIC_TITLE.sub(lambda _m: title, wt)
    wt = _MAGIC_GAME.sub("Enshrouded", wt)
    wt = _MAGIC_DROP.sub("", wt)
    return wt


def fetch_wikitexts(titles):
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
                out[page["title"]] = expand_magic(
                    page["revisions"][0]["slots"]["main"]["*"], page["title"]
                )
        time.sleep(0.5)
    return out


def parse_template(wikitext, name):
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
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"'{2,}", "", s)
    s = re.sub(r"<br\s*/?>", ", ", s, flags=re.I)
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    # 兜底：清掉被截断的模板尾巴与孤立括号（残留形如 '… every sorcerer. {{About Staves'）
    s = re.sub(r"\{\{[^{}]*$", "", s)
    s = s.replace("}}", "").replace("{{", "")
    return s.strip()


def lead_prose(wt: str) -> str:
    """取条目导语段落（开头 infobox 模板之后、第一个 == 标题之前）。

    旧写法 re.search(r"\\}\\}(.*?)==", wt, re.S) 用「第一个 }}」定位导语起点：
    只要正文出现任何内联模板（如 {{SUBPAGENAME}}、{{item+iconright|X}}），
    就会从模板中途开始截 —— 导语变成 "''' is a level 13 …" 或 "to unlock."。
    正确做法：按括号深度剥掉开头的模板块，再截到第一个二级标题。
    """
    t = re.sub(r"<!--.*?-->", "", wt, flags=re.S)
    t = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", "", t)
    while True:                                   # 剥掉开头连续的 {{...}} 块
        m = re.search(r"\{\{", t)
        if not m or t[: m.start()].strip():
            break
        depth, j = 0, m.start()
        while j < len(t):
            if t[j] == "{":
                depth += 1
            elif t[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        t = t[: m.start()] + t[j + 1 :]
    t = re.split(r"^={2,}", t, flags=re.M)[0]     # 截到第一个二级标题
    return re.sub(r"\s+", " ", clean(t)).strip()


def parse_ingredients(s):
    out = []
    for part in re.split(r",", s):
        m = re.match(r"\s*(.+?):\s*(\d+)\s*$", part)
        if m:
            out.append({"name": clean(m.group(1)), "qty": int(m.group(2))})
    return out


def slugify(title):
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def main():
    # ---- 单件护甲 ----
    piece_titles = {}
    for cat in PIECE_CATS:
        titles = list_category(cat)
        for t in titles:
            piece_titles.setdefault(t, cat)
        print(f"{cat}: {len(titles)} 个页面")
    pkeys = sorted(piece_titles)
    print(f"共 {len(pkeys)} 个护甲单件，抓取 wikitext...")
    texts = fetch_wikitexts(pkeys)

    pieces = []
    for t in pkeys:
        wt = texts.get(t, "")
        infobox = parse_template(wt, "Armor Infobox")
        stats = parse_template(wt, "Armor Stats")
        if not infobox:
            continue
        set_m = re.search(r"part of the \[\[([^\]|]+)", wt)
        craft = parse_template(wt, "Crafting")
        pieces.append({
            "name": t,
            "slug": slugify(t),
            "slot": clean(infobox.get("type", "")),
            "armorClass": clean(infobox.get("armorclass", "")),
            "category": PIECE_CATS[piece_titles[t]],
            "level": clean(infobox.get("level", "")),
            "rarity": clean(infobox.get("rarity", "")),
            "physical": clean(stats.get("physical", "")),
            "magical": clean(stats.get("magical", "")),
            "effect": clean(stats.get("effect1", "")),
            "set": clean(set_m.group(1)) if set_m else "",
            "crafter": clean(craft.get("crafter", "")),
            "ingredients": parse_ingredients(craft.get("ingredients", "")),
            "description": clean(infobox.get("description", "")),
            "image": infobox.get("images", "").split(",")[0].strip(),
        })
    pieces.sort(key=lambda x: (x["category"], x["name"].lower()))

    # ---- 套装 ----
    set_titles = list_category("Armor Set")
    print(f"共 {len(set_titles)} 个套装，抓取 wikitext...")
    stexts = fetch_wikitexts(set_titles)
    sets = []
    for t in set_titles:
        wt = stexts.get(t, "")
        tpl = parse_template(wt, "Armor Set")
        lv = re.search(r"is a level (\d+)", wt)
        intro_text = lead_prose(wt)
        cls = re.search(r"\[\[Armor/(Melee|Magic|Ranged)", wt)
        sets.append({
            "name": t,
            "slug": slugify(t),
            "level": lv.group(1) if lv else "",
            "class": (cls.group(1).lower() if cls else ""),
            "pieces": [clean(p) for p in tpl.get("_positional", [])],
            "summary": intro_text[:300],
        })
    sets.sort(key=lambda x: x["name"].lower())

    import os
    base = os.path.join(os.path.dirname(__file__), "..", "src", "data")
    os.makedirs(base, exist_ok=True)
    with open(os.path.join(base, "armor.json"), "w", encoding="utf-8") as f:
        json.dump(pieces, f, ensure_ascii=False, indent=2)
    with open(os.path.join(base, "armor-sets.json"), "w", encoding="utf-8") as f:
        json.dump(sets, f, ensure_ascii=False, indent=2)
    print(f"写入 {len(pieces)} 件护甲 + {len(sets)} 个套装 -> {base}")


if __name__ == "__main__":
    main()
