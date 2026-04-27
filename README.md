# Plonker

Chrome extension that hooks GeoGuessr, tracks your rounds, and surfaces meta tips
from [plonkit.net](https://www.plonkit.net) and [learnablemeta.com](https://learnablemeta.com)
right after you guess. Stats sync to a personal Supabase project so they survive a
browser reset and let you slice your weak countries later.

See [SPEC.md](SPEC.md) and [docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md) for the
full design.

## Install (dev)
1. `git checkout dev`
2. Open `chrome://extensions` in Chrome.
3. Toggle **Developer mode** (top right).
4. **Load unpacked** → pick `extension/` folder.
5. Visit `https://www.geoguessr.com/`, play a round, observe the post-round overlay.

## Re-scraping tip data

The bundle in `extension/data/tips.json` is rebuilt from two scraped sources:
- `scraper/plonkit_raw.json` — per-country narrative content from plonkit.net
- `scraper/learnablemeta_raw.json` — atomic country-tagged metas from
  learnablemeta.com

```bash
pip install -r scraper/requirements.txt
python -m playwright install chromium    # one-time
pip install easyocr                       # for OCR on plonkit map insets

python scraper/scrape_plonkit.py          # ~10 min, all countries
python scraper/scrape_learnablemeta.py    # ~5 min, all 46 maps
python scraper/download_images.py         # ~20 min, ~5000 images, ~200 MB
python scraper/ocr_plonkit.py             # ~30 min, EasyOCR on plonkit images
python scraper/build_bundle.py            # writes extension/data/tips.json
```

## Adding a new tip source

If you find a learnablemeta map that's not yet bundled (or want a freshly-added
plonkit country), add it and re-scrape:

### Adding a learnablemeta map
1. Find the map ID in the URL: `https://learnablemeta.com/maps/<this-id>`
2. Add it to `MAP_IDS` in `scraper/scrape_learnablemeta.py` AND to
   `LEARNABLE_META_MAP_IDS` in `extension/src/data/learnable-meta-map-ids.js`
   (so the in-game tracker also knows it's a learnable-meta map).
3. Re-scrape:
   ```bash
   python scraper/scrape_learnablemeta.py
   python scraper/download_images.py
   python scraper/build_bundle.py
   ```
4. Bump `extension/manifest.json` version, reload in Chrome.

### Adding a country plonkit doesn't cover yet
Plonkit's sitemap auto-discovers new country pages — just re-run the full pipeline:
```bash
python scraper/scrape_plonkit.py
python scraper/download_images.py
python scraper/ocr_plonkit.py
python scraper/build_bundle.py
```

If the country has rich sub-region content, add it to `KNOWN_SUBDIVISIONS` in
both `scraper/build_bundle.py` AND `scraper/ocr_plonkit.py` so its regional
tips get tagged correctly.

### Asking the bot

Easier: tell Claude *"add tips from <learnablemeta or plonkit URL>"* and it'll
do all of the above.

## Layout
- `extension/` — the unpacked Chrome MV3 extension.
  - `data/tips.json` — the bundled per-country tip database.
  - `assets/img/` — downloaded plonkit + learnablemeta images.
  - `src/` — manifest, content script, background service worker, popup, overlay.
- `scraper/` — Python tools that produce `tips.json`.
- `docs/SUPABASE_SCHEMA.sql` — the schema applied to Supabase project
  `qhudavmfhbumknqddgig`.
- `SPEC.md`, `docs/DATA_PIPELINE.md` — design docs.
