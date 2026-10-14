// src/lib/builds.ts — class ↔ weapon-category mapping for cross-category links.
//
// WHY THIS EXISTS
// Search Console showed the 293 weapon pages with zero impressions while armour
// and consumable pages were crawled. The cause was not content quality: Google
// had indexed a handful of armour/consumable pages, had never crawled the weapon
// branch, and — crucially — no *indexed* page linked to any *weapon* page. The
// only inbound links to a weapon page came from /weapons/ and from other weapon
// pages, none of which Google had crawled, so the whole branch was unreachable.
//
// Enshrouded ties armour class and weapon choice together through its build
// system (Melee / Ranged / Magic), so cross-linking them is genuinely useful to
// a reader — and it gives Google a crawl path from pages it already knows to the
// pages it does not.

export type BuildClass = "melee" | "ranged" | "magic";

/** Armour class → weapon categories a player of that class actually uses. */
export const CLASS_WEAPONS: Record<BuildClass, string[]> = {
  melee: [
    "One-handed Swords",
    "One-handed Axes",
    "One-handed Clubs",
    "Daggers",
    "Two-handed Greatswords",
    "Two-handed Hammers",
    "Two-handed Axes",
    "Two-handed Clubs",
  ],
  ranged: ["Bows", "Throwing Weapons"],
  magic: ["Wands", "Staves"],
};

/** Weapon category → its armour class (reverse of the map above). */
export const WEAPON_CLASS: Record<string, BuildClass> = Object.fromEntries(
  (Object.keys(CLASS_WEAPONS) as BuildClass[]).flatMap((cls) =>
    CLASS_WEAPONS[cls].map((cat) => [cat, cls] as const),
  ),
);

export const CLASS_LABEL: Record<BuildClass, string> = {
  melee: "Melee",
  ranged: "Ranged",
  magic: "Magic",
};

/** Armour `category` values that map onto a build class (drops "misc"). */
export function isBuildClass(v: unknown): v is BuildClass {
  return v === "melee" || v === "ranged" || v === "magic";
}

/**
 * Parse a level that may be "40", "45+", "35-40", "" or junk ("XXX").
 * Returns 0 for anything unusable so it sorts last instead of first.
 */
export function levelOf(v: unknown): number {
  const m = /(\d+)/.exec(String(v ?? ""));
  return m ? parseInt(m[1], 10) : 0;
}

/** Highest-level first, using `levelOf`; stable for equal levels. */
export function topByLevel<T extends { level?: string }>(items: T[], n: number): T[] {
  return [...items]
    .sort((a, b) => levelOf(b.level) - levelOf(a.level))
    .slice(0, n);
}

/**
 * Items closest in level to `target`.
 *
 * Deliberately not `topByLevel`: if every armour page linked the same eight
 * highest-level weapons, only those eight weapons would ever gain an inbound
 * link from a page Google has crawled. Matching by level instead spreads the
 * links across the whole catalogue — and it is also the more useful answer, a
 * Lv 5 armour piece has no business recommending a Lv 50 weapon.
 *
 * `seed` (usually the page's own slug) rotates the pick inside a window of the
 * `n * 3` closest items, so two pieces at the same level recommend overlapping
 * but different weapons instead of the identical eight. Without it, coverage
 * stalls at whatever fits in one window.
 */
export function nearestByLevel<T extends { level?: string }>(
  items: T[],
  target: number,
  n: number,
  seed = "",
): T[] {
  if (!target) return topByLevel(items, n);
  const sorted = [...items].sort(
    (a, b) => Math.abs(levelOf(a.level) - target) - Math.abs(levelOf(b.level) - target),
  );
  if (!seed) return sorted.slice(0, n);
  const window = sorted.slice(0, Math.min(sorted.length, n * 3));
  const off = hash(seed) % window.length;
  return Array.from({ length: Math.min(n, window.length) }, (_, i) => window[(off + i) % window.length]);
}

/** Deterministic string hash — same seed always yields the same rotation. */
function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

/**
 * Wiki exports repeat perks (a weapon's perk pool is stored as a 5-slot roll, so
 * "Piercing Damage" can appear twice). Deduplicate for display, keeping order.
 */
export function uniquePerks(perks?: string[]): string[] {
  if (!Array.isArray(perks)) return [];
  const out: string[] = [];
  for (const p of perks) {
    const s = String(p ?? "").trim();
    if (s && !out.includes(s)) out.push(s);
  }
  return out;
}

/** "XXX" and friends are wiki placeholders, not data — render nothing instead. */
export function stat(v: unknown): string {
  const s = String(v ?? "").trim();
  return !s || /^x+$/i.test(s) ? "" : s;
}
