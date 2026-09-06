import type { APIRoute } from "astro";
import armor_sets_data from "../data/armor-sets.json";
import armor_data from "../data/armor.json";
import consumables_data from "../data/consumables.json";
import items_data from "../data/items.json";
import weapons_data from "../data/weapons.json";

const tools: Array<{ t: string; u: string; k: string; i?: string }> = [{"t": "Damage & Resistance Rankings", "u": "/rankings/", "k": "Tool"}, {"t": "Materials Calculator", "u": "/materials-calculator/", "k": "Tool"}];

const items: Array<{ t: string; u: string; k: string; i?: string }> = [
  ...armor_sets_data.map((x: any) => { const n = x.name || x.title; if (!n || !x.slug) return null; if (n.includes("/") || String(x.slug).includes("/")) return null; return { t: n, u: `/armor-sets/${x.slug}/`, k: "Armor sets", i: x.icon || "" }; }).filter(Boolean) as Array<{t:string;u:string;k:string;i:string}>,
  ...armor_data.map((x: any) => { const n = x.name || x.title; if (!n || !x.slug) return null; if (n.includes("/") || String(x.slug).includes("/")) return null; return { t: n, u: `/armor/${x.slug}/`, k: "Armor", i: x.icon || "" }; }).filter(Boolean) as Array<{t:string;u:string;k:string;i:string}>,
  ...consumables_data.map((x: any) => { const n = x.name || x.title; if (!n || !x.slug) return null; if (n.includes("/") || String(x.slug).includes("/")) return null; return { t: n, u: `/consumables/${x.slug}/`, k: "Consumables", i: x.icon || "" }; }).filter(Boolean) as Array<{t:string;u:string;k:string;i:string}>,
  ...items_data.map((x: any) => { const n = x.name || x.title; if (!n || !x.slug) return null; if (n.includes("/") || String(x.slug).includes("/")) return null; return { t: n, u: `/items/${x.slug}/`, k: "Items", i: x.icon || "" }; }).filter(Boolean) as Array<{t:string;u:string;k:string;i:string}>,
  ...weapons_data.map((x: any) => { const n = x.name || x.title; if (!n || !x.slug) return null; if (n.includes("/") || String(x.slug).includes("/")) return null; return { t: n, u: `/weapons/${x.slug}/`, k: "Weapons", i: x.icon || "" }; }).filter(Boolean) as Array<{t:string;u:string;k:string;i:string}>,
];

export const GET: APIRoute = () =>
  new Response(JSON.stringify({ tools, items }), {
    headers: { "Content-Type": "application/json" },
  });
