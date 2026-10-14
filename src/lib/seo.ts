// src/lib/seo.ts  —  EmberDB (Enshrouded) answer-first <meta description> builders.
//
// Problem this solves: the four detail templates used to emit a zero-information
// prefix ("Enshrouded X: effects, duration, rarity and how to craft it.") followed
// by a blindly sliced wiki blurb. For the 63/181 consumables with no wiki blurb the
// description was 100% boilerplate, and for the rest the front-loaded clause carried
// no values at all. Search Console shows EmberDB's impressions are concentrated in
// consumables at positions 4-11 with CTR ~0 — i.e. the snippet is the problem.
//
// Rule: the first clause must carry concrete, retrievable values (effects, stats,
// level, where to find). Never print a placeholder; if a field is empty, drop it.
// Clauses are assembled whole — a clause that does not fit is dropped, never sliced.

type Ing = { name?: string; qty?: number | string };

export type Consumable = {
  name: string;
  group?: string;
  rarity?: string;
  duration?: string;
  effects?: string[];
  crafter?: string;
  craftTime?: string;
  ingredients?: Ing[];
  description?: string;
};

export type Weapon = {
  name: string;
  type?: string;
  category?: string;
  level?: string;
  attackSpeed?: string;
  perks?: string[];
  source?: string[];
  description?: string;
};

export type ArmorPiece = {
  name: string;
  slot?: string;
  armorClass?: string;
  category?: string;
  level?: string;
  rarity?: string;
  physical?: string;
  magical?: string;
  effect?: string;
  set?: string;
  crafter?: string;
  ingredients?: Ing[];
  description?: string;
};

export type ArmorSet = {
  name: string;
  level?: string;
  class?: string;
  pieces?: string[];
  summary?: string;
};

const MAX = 158;
const MIN = 60;

// Values that look like data but mean "no data".
const SENTINELS = new Set([
  "", "none", "n/a", "na", "unknown", "null", "undefined", "-", "--", "—", "?", "0",
]);

// Words that must not end a truncated description.
const DANGLING = new Set([
  "from", "by", "in", "the", "and", "with", "of", "to", "at", "for", "on", "or", "a", "an", "into",
]);

/** Normalise a scalar: strip wiki markup / icon residue, collapse whitespace. */
function clean(v: unknown): string {
  if (v === null || v === undefined) return "";
  let s = String(v).trim();
  if (SENTINELS.has(s.toLowerCase())) return "";
  s = s.replace(/\[\[([^\]|]+)(?:\|[^\]]*)?\]\]/g, "$1"); // [[A|B]] -> A
  s = s.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");           // [A](url) -> A
  s = s.replace(/\{\{[^}]*\}\}/g, "");                      // {{templates}}
  s = s.replace(/<[^>]*>/g, " ");                           // html tags
  s = s.replace(/[ \t\u00a0]+/g, " ");
  return s.trim();
}

/** Game stat strings read badly with a space after the sign: "+ 60" -> "+60". */
function fx(v: unknown): string {
  return clean(v).replace(/\+\s+/g, "+").replace(/-\s+(?=\d)/g, "-");
}

function list(v: unknown, n = 3): string[] {
  if (!Array.isArray(v)) return [];
  const out: string[] = [];
  for (const x of v) {
    const s = fx(x);
    if (s && !out.includes(s)) out.push(s);
    if (out.length >= n) break;
  }
  return out;
}

function names(v: unknown, n = 3): string[] {
  if (!Array.isArray(v)) return [];
  const out: string[] = [];
  for (const x of v as Ing[]) {
    const s = clean(x && (x.name ?? x));
    if (s && !out.includes(s)) out.push(s);
    if (out.length >= n) break;
  }
  return out;
}

/** Pick the most informative sentence from a wiki blurb (prefer one with a number). */
function leadSentence(text?: string, max = 120): string {
  const s = clean(text);
  if (!s) return "";
  const parts = s.split(/(?<=[.!?])\s+/).filter(Boolean);
  const chosen = parts.find((p) => /\d/.test(p)) ?? parts[0] ?? s;
  return chosen.length > max ? chosen.slice(0, max).replace(/[\s,;:.]+$/, "") : chosen;
}

function tidy(s: string): string {
  return s.replace(/\s+/g, " ").replace(/\s+([,.;:])/g, "$1").replace(/,\s*,/g, ",").trim();
}

/** Hard-cut to max chars at a boundary, then drop any trailing dangling word. */
function hardFit(s: string, max = MAX): string {
  let t = tidy(s);
  if (t.length > max) {
    t = t.slice(0, max);
    const cut = Math.max(t.lastIndexOf(". "), t.lastIndexOf(", "), t.lastIndexOf(" "));
    if (cut > max * 0.6) t = t.slice(0, cut);
  }
  for (let i = 0; i < 4; i++) {
    t = t.replace(/[\s,;:.]+$/, "");
    const w = t.slice(t.lastIndexOf(" ") + 1).toLowerCase();
    if (!DANGLING.has(w)) break;
    t = t.slice(0, t.lastIndexOf(" "));
  }
  t = t.replace(/[\s,;:.]+$/, "");
  if (t && !/[.!?]$/.test(t)) t += ".";
  return t;
}

/** Assemble head + whole clauses, dropping any clause that would overflow. */
function assemble(head: string, clauses: string[], fallbackLead: string): string {
  const h = clean(head);
  const cs = clauses.map(tidy).filter(Boolean);
  const used = [h];
  for (const c of cs) {
    if (tidy([...used, c].join(" ")).length <= MAX) used.push(c);
    else break;
  }
  let out = tidy(used.join(" ")).replace(/[\s,;:.]+$/, "");
  if (!/[.!?]$/.test(out)) out += ".";
  if (out.length < MIN) {
    // Nothing meaningful fit — splice in the original prose lead, then hard-cut.
    const lead = leadSentence(fallbackLead);
    if (lead) out = hardFit(`${out} ${lead}`);
  }
  return out.length > MAX ? hardFit(out) : out;
}

/** Some groups are too long/noisy to sit in a snippet ("Potions & Consumable Items"). */
function groupWord(group?: string): string {
  const g = clean(group);
  return g && g.length <= 18 && !/[&/]/.test(g) ? g : "consumable";
}

export function consumableDesc(c: Consumable): string {
  const g = groupWord(c.group);
  const effects = list(c.effects, 3);
  const dur = clean(c.duration);
  const crafter = clean(c.crafter);
  const ings = names(c.ingredients, 3);

  const clauses: string[] = [];
  if (effects.length) clauses.push(`Grants ${fx(effects.join(", "))}.`);
  if (dur) clauses.push(/^instant$/i.test(dur) ? "Instant effect." : `Lasts ${dur}.`);
  if (crafter && ings.length) clauses.push(`Crafted by the ${crafter} from ${ings.join(", ")}.`);
  else if (crafter) clauses.push(`Crafted by the ${crafter}.`);
  else if (ings.length) clauses.push(`Crafted from ${ings.join(", ")}.`);

  const head = `${clean(c.name)} — Enshrouded ${g === "consumable" ? "" : `${g} `}consumable.`;
  return assemble(head, clauses, c.description || "");
}

export function weaponDesc(w: Weapon): string {
  const type = clean(w.type) || clean(w.category) || "weapon";
  const lvl = clean(w.level);
  const perks = list(w.perks, 3);
  const src = list(w.source, 2);
  const spd = clean(w.attackSpeed);

  const clauses: string[] = [];
  if (perks.length) clauses.push(`Perks: ${perks.join(", ")}.`);
  if (spd) clauses.push(`Attack speed ${spd}.`);
  if (src.length) clauses.push(`Found in ${src.join(", ")}.`);

  const head = `${clean(w.name)} — Enshrouded ${type}${lvl ? `, level ${lvl}` : ""}.`;
  return assemble(head, clauses, w.description || "");
}

export function armorDesc(a: ArmorPiece): string {
  const slot = clean(a.slot) || "armor piece";
  const cls = clean(a.armorClass) || clean(a.category);
  const lvl = clean(a.level);
  const rarity = clean(a.rarity);
  const phys = clean(a.physical);
  const mag = clean(a.magical);
  const effect = clean(a.effect);
  const set = clean(a.set);
  const ings = names(a.ingredients, 3);

  const clauses: string[] = [];
  if (phys || mag) {
    const stats = [phys && `physical ${phys}`, mag && `magical ${mag}`].filter(Boolean).join(", ");
    clauses.push(`${stats.charAt(0).toUpperCase()}${stats.slice(1)}.`);
  }
  if (effect) clauses.push(`${effect}.`);
  if (rarity) clauses.push(`${rarity}.`);
  if (set) clauses.push(`Part of the ${set}.`);
  else if (ings.length) clauses.push(`Crafted from ${ings.join(", ")}.`);

  // "Foot Armor (Magic armor, ...)" double-prints "armor" — drop the class suffix
  // when the slot name already contains it.
  const clsLabel = cls && (/armou?r|piece/i.test(slot) ? cls : `${cls} armor`);
  const meta = [clsLabel, lvl && `level ${lvl}`].filter(Boolean).join(", ");
  const head = `${clean(a.name)} — Enshrouded ${slot}${meta ? ` (${meta})` : ""}.`;
  return assemble(head, clauses, a.description || "");
}

export function setDesc(s: ArmorSet): string {
  const lvl = clean(s.level);
  const cls = clean(s.class);
  const pieces = list(s.pieces, 5);
  // The set summary is original prose that already carries level/class/count, so it
  // is strictly better than anything we can rebuild — use it verbatim when present.
  const summary = clean(s.summary);
  if (summary) return hardFit(summary);
  const built =
    `${clean(s.name)} is a${cls ? ` ${cls}` : ""} armor set in Enshrouded` +
    `${lvl ? `, level ${lvl}` : ""}${pieces.length ? `, with ${pieces.length} pieces` : ""}.`;
  return hardFit(built);
}
