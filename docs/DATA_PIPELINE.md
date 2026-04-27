# Plonker data pipeline v2

## Sources audited (2026-04-26)

### plonkit.net (Vite/React SPA)
- One page per country at `/{slug}`. Hydrates client-side, so requires Playwright.
- DOM structure on a country page:
  - `<h1>` country name
  - `<h3>` "Step 1 - Identifying X" / "Step 1.1 - Different from..." / "Step 2 - Regional clues" / "Step 3 - Spotlight" / "Step 4 - Maps and resources" / "Other resources"
  - **No `<h4>` sub-headings**, **no `<figure>` or `<figcaption>`**, **alt text always empty**
  - Loose `<img>` tags interleaved with `<p>` content in reading order
- **The image filenames carry the strongest semantic signal.** Examples from Ireland:
  - `Donegal_Gen_4_roads.png` → tag region: Donegal
  - `Wicklow_mountains.png` → tag region: Wicklow
  - `Cork_hilly_city.png` → tag region: Cork
  - `ie_phonecodes.png` → flag general rule: phone codes
  - `Ireland-road-numbers2.png` → flag general rule: road numbers
- Per-country page conventionally orders items as IMAGE → TEXT-describing-image → next IMAGE → next TEXT.

### learnablemeta.com (SvelteKit SPA)
- One page per map at `/maps/{id}`. ~46 maps in our allowlist.
- Data is embedded in a `<script>` containing the hydration payload — search for `metaList:[...]`.
- Each meta is a clean atomic record:
  ```json
  {
    "id": 159,
    "name": "Australia - Bollard",
    "note": "<p>Australian bollards are white with a red reflector on the front and grey on the back.</p>\n<p>Turkish bollards are similar but lack a back reflector. If unsure, check the sun position, landscape, or vegetation.</p>",
    "images": ["https://learnablemeta.com/images/{hash}.avif"],
    "locationsCount": "20",
    "footer": "Description and images taken from: ..."
  }
  ```
- Format of `name`: `{Country} - {MetaDescription}`. The country part is reliable; the description is human-curated and short.
- `note` is HTML with comparisons baked in (`X is similar but Y differs because...`).
- Typically 1 image per meta, hosted on learnablemeta's AVIF CDN.

## Why current pipeline produces bad tips

1. **Prose place extraction is noisy.** Regex on plonkit text picks up "Like", "If", "These", country adjectives, etc.
2. **The most reliable region signal (image filenames) is ignored.** Filenames like `Donegal_Gen_4_roads.png` are wasted.
3. **Learnablemeta is unused.** We have a clean structured source with comparisons and we're scraping the messy prose source instead.
4. **Country-wide rules get place-tagged** because they happen to mention specific cities as examples.
5. **Image→text association was wrong direction**, partially fixed in v0.6.1.

## New data shape

Per-country, ISO-2 keyed:

```json
{
  "AU": {
    "name": "Australia",
    "plonkit_slug": "australia",

    "metas": [
      {
        "type": "Bollard",
        "title": "Australia - Bollard",
        "description": "Australian bollards are white with a red reflector on the front and grey on the back.",
        "comparison": "Turkish bollards are similar but lack a back reflector. If unsure, check the sun position, landscape, or vegetation.",
        "images": ["https://learnablemeta.com/images/...avif"],
        "from_maps": ["A Learnable Meta World - Basics"]
      },
      ...
    ],

    "general_rules": [
      {
        "topic": "Road numbers",
        "text": "Irish regional roads have 3-digit road numbers...",
        "images": ["https://www.plonkit.net/images/.../Ireland-road-numbers2.png"]
      },
      ...
    ],

    "regions": {
      "Donegal":  [{ "text": "...", "images": [...] }, ...],
      "Wicklow":  [{ "text": "...", "images": [...] }, ...]
    },

    "spotlight": [
      { "place": "Cairns",  "text": "...", "images": [...] },
      { "place": "Tom Price", "text": "...", "images": [...] }
    ]
  }
}
```

## Tab mapping

- **Identify** → `metas[]` (learnablemeta-curated, atomic, with comparisons)
- **General**  → `general_rules[]` (system-wide rules pulled from plonkit Step 2)
- **Regional** → `regions[Y]` where `Y` is matched against the round's geocoded place names
- **Spotlight**→ `spotlight[]` filtered by `place` overlap with the round's geocoded names
- **Images**   → aggregate of all
- **Notes**    → user notes

## Region-tag extraction (replaces regex on prose)

For plonkit items, the region tag comes from the image filename:
1. Strip prefix: `https://www.plonkit.net/images/resize/{w}/{q}/{country}/`
2. Take filename without extension.
3. Match against a per-country list of known sub-region names (Donegal, Wicklow, Cork, etc.).
4. The text item that follows the image inherits the image's tag.

This eliminates the entire `extract_places` regex + stop-list machinery for region tagging on plonkit-derived content.

## Building the per-country sub-region list

For each country, walk every plonkit image filename and harvest tokens that look like place names:
- Split on `_`, `-`, drop digits and short tokens.
- Collect tokens that show up across multiple country pages → treat as known regions.
- Cross-reference with Wikipedia's per-country admin division list (could embed as a static lookup).

For v1, we manually seed the lookup with the well-known subdivisions of the major countries (US states, German Bundesländer, French régions, Italian regions, Australian states, Russian federal subjects, etc.).

## Cron / refresh

- `python scraper/scrape_plonkit.py` — pulls all country pages.
- `python scraper/scrape_learnablemeta.py` — pulls all map metaLists.
- `python scraper/build_bundle.py` — merges into `extension/data/tips.json`.

Run monthly; bump bundle `_meta.version`.
