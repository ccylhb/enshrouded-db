# -*- coding: utf-8 -*-
"""Enshrouded wiki.gg 消耗品抓取管道
用法: python scrape_consumables.py
输出: ../src/data/consumables.json
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://enshrouded.wiki.gg/api.php"
UA = "EmberDB-scraper/1.0 (site data pipeline)"


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


DRINK_WORDS = ("tea", "coffee", "latte", "mokka", "milk", "smoothie", "water")
POTION_WORDS = ("potion", "flask", "elixir", "tonic", "scroll", "antidote", "bandage",
                "lotion", "pocket heater", "wisp")


def classify(name, desc):
    n = name.lower()
    if any(w in n for w in POTION_WORDS):
        return "Potions & Consumable Items"
    if any(w in n for w in DRINK_WORDS):
        return "Drinks"
    return "Food"


def main():
    titles = sorted(set(list_category("Consumables")))
    print(f"共 {len(titles)} 个消耗品页面，抓取 wikitext...")
    texts = fetch_wikitexts(titles)

    items = []
    for t in titles:
        wt = texts.get(t, "")
        infobox = parse_template(wt, "Item Infobox")
        stats = parse_template(wt, "ItemStats")
        craft = parse_template(wt, "Crafting")
        if not infobox and not stats:
            continue
        effects = [clean(v) for k, v in stats.items()
                   if k.startswith("effects") and clean(v)]
        items.append({
            "name": t,
            "slug": slugify(t),
            "group": classify(t, ""),
            "rarity": clean(infobox.get("rarity", "")),
            "stackSize": clean(infobox.get("stacksize", "")),
            "duration": clean(stats.get("duration", "")),
            "effects": effects,
            "crafter": clean(craft.get("crafter", "")),
            "craftTime": clean(craft.get("crafting time", "")),
            "ingredients": parse_ingredients(craft.get("ingredients", "")),
            "description": clean(infobox.get("description", "")),
            "image": infobox.get("images", "").split(",")[0].strip(),
        })
    items.sort(key=lambda x: (x["group"], x["name"].lower()))

    import os
    out_path = os.path.join(os.path.dirname(__file__), "..", "src", "data", "consumables.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"写入 {len(items)} 条消耗品 -> {out_path}")


if __name__ == "__main__":
    main()
