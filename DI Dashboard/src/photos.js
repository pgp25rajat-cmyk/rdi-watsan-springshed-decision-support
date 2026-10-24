// Field photos from the October 2026 visit, by DI handpump name (Rajat's Pictures folder, resized).
export const PUMP_PHOTOS = {
  "Arakot 1": [
    {
      src: "photos/arakot-1/1.jpg",
      caption: "Arakot 1 DI handpump",
    },
    {
      src: "photos/arakot-1/2.jpg",
      caption: "Rooftop that feeds the Arakot 1 DI line",
    },
    {
      src: "photos/arakot-1/3.jpg",
      caption: "Broken roof pipe on the Arakot 1 DI line",
    },
    {
      src: "photos/arakot-1/4.jpg",
      caption: "Measuring flow at Balench spring",
      spring: "Balench",
    },
  ],
  "Arakot 2": [
    {
      src: "photos/arakot-2/1.jpg",
      caption: "Testing the Arakot 2 DI handpump",
    },
    {
      src: "photos/arakot-2/2.jpg",
      caption: "Arakot 2 DI handpump",
    },
    {
      src: "photos/arakot-2/3.jpg",
      caption: "Paniyar Dhar spring tank",
      spring: "Paniyar Dhar",
    },
    {
      src: "photos/arakot-2/4.jpg",
      caption: "Paniyar Dhar spring outlet",
      spring: "Paniyar Dhar",
    },
  ],
  "Chopriyal 1": [
    {
      src: "photos/chopriyal-1/1.jpg",
      caption: "Chopriyal 1 DI handpump",
    },
    {
      src: "photos/chopriyal-1/2.jpg",
      caption: "Chorghadna spring at the Churerdhar solar pumping site",
      spring: "Chorghadna",
    },
  ],
  "Chopriyal 2": [
    {
      src: "photos/chopriyal-2/1.jpg",
      caption: "Chopriyal 2 DI handpump",
    },
    {
      src: "photos/chopriyal-2/2.jpg",
      caption: "Nimbujhard spring outlet",
      spring: "Nimbujhard",
    },
    {
      src: "photos/chopriyal-2/3.jpg",
      caption: "Water sample from the Chopriyal 2 handpump",
    },
    {
      src: "photos/chopriyal-2/4.jpg",
      caption: "Field team at Nimbujhard spring",
      spring: "Nimbujhard",
    },
  ],
  Gunogi: [
    {
      src: "photos/gunogi/1.jpg",
      caption: "Malani spring outlet",
      spring: "Malani",
    },
    {
      src: "photos/gunogi/2.jpg",
      caption: "Malani spring and the slope above it",
      spring: "Malani",
    },
  ],
  Kanatal: [
    {
      src: "photos/kanatal/1.jpg",
      caption: "Kanatal DI handpump",
    },
    {
      src: "photos/kanatal/2.jpg",
      caption: "Rasanulikhal spring tank",
      spring: "Rasanulikhal",
    },
    {
      src: "photos/kanatal/3.jpg",
      caption: "Slope above Rasanulikhal spring",
      spring: "Rasanulikhal",
    },
  ],
  Kaddukhal: [
    {
      src: "photos/kaddukhal/1.jpg",
      caption: "Kaddukhal DI handpump, broken",
    },
    {
      src: "photos/kaddukhal/2.jpg",
      caption: "Ganjrkhanal spring (naula)",
      spring: "Ganjrkhanal",
    },
    {
      src: "photos/kaddukhal/3.jpg",
      caption: "Building next to the Kaddukhal handpump",
    },
  ],
  Kunjapuri: [
    {
      src: "photos/kunjapuri/1.jpg",
      caption: "Kunjapuri DI handpump",
    },
    {
      src: "photos/kunjapuri/2.jpg",
      caption: "Kunjapuri DI handpump and roof pipe",
    },
  ],
};

// A photo with a spring name shows on that spring's page only.
const BASE = import.meta.env.BASE_URL || "/";
const key = (name) =>
  String(name || "")
    .trim()
    .toLowerCase();
const BY_KEY = Object.fromEntries(Object.entries(PUMP_PHOTOS).map(([k, v]) => [key(k), v]));

export const pumpPhotos = (name) => (BY_KEY[key(name)] || []).map((p) => ({ ...p, url: BASE + p.src }));

// Every DI handpump linked to a site, primary first. Imported sites carry one list; portal sites keep the
// selected handpump and the additional ones separately.
export function sitePumps(s) {
  if (s.handpumps?.length) return s.handpumps.map((h) => ({ name: h.name, primary: !!h.primary }));
  return [
    ...(s.handpump_name ? [{ name: s.handpump_name, primary: true }] : []),
    ...(s.additional_handpumps || []).map((h) => ({ name: h.name, primary: false })),
  ];
}

// One entry per handpump name, with the springs (sites) it is linked to. The spring where the handpump is
// the selected one comes first.
export function handpumpGroups(sites) {
  const groups = new Map();
  for (const s of sites)
    for (const p of sitePumps(s)) {
      if (!p.name) continue;
      const k = key(p.name);
      if (!groups.has(k)) groups.set(k, { name: p.name.trim(), sites: [] });
      const g = groups.get(k);
      if (!g.sites.some((x) => x.id === s.id)) g.sites[p.primary ? "unshift" : "push"](s);
    }
  return [...groups.values()];
}

export const sitePhotos = (s) =>
  sitePumps(s)
    .flatMap((p) => pumpPhotos(p.name))
    .filter((p) => !p.spring || p.spring === (s.spring_name || s.name));
