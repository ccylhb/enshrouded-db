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
                out[page["title"]] = page["revisions"][0]["slots"]["main"]["*"]
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
    return s.strip()


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
        intro = re.search(r"\}\}(.*?)==", wt, re.S)
        intro_text = clean(intro.group(1)) if intro else ""
        intro_text = re.sub(r"\s+", " ", intro_text).strip()
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
