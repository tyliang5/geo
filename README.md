# Plonker

Chrome extension that hooks GeoGuessr, tracks your rounds, and surfaces meta tips
from [plonkit.net](https://www.plonkit.net) and [learnablemeta.com](https://learnablemeta.com)
right after you guess. Stats sync to a personal Supabase project so they survive a
browser reset and let you slice your weak countries later.

See [SPEC.md](SPEC.md) for the locked feature list (output of a 40-question discovery).

## Install (dev)
1. `git checkout dev`
2. Open `chrome://extensions` in Chrome on Ty laptop.
3. Toggle **Developer mode** (top right).
4. **Load unpacked** -> pick `extension/` folder.
5. Visit `https://www.geoguessr.com/`, play a round, observe the post-round overlay.

## Re-scraping tip data
```bash
pip install -r scraper/requirements.txt
python scraper/scrape_plonkit.py
python scraper/scrape_learnablemeta.py
python scraper/build_bundle.py        # writes extension/data/tips.json
```

## Layout
- `extension/` - the unpacked Chrome MV3 extension.
- `scraper/` - Python tools that distill plonkit + learnablemeta into `tips.json`.
- `docs/SUPABASE_SCHEMA.sql` - the schema applied to project `qhudavmfhbumknqddgig`.
- `SPEC.md` - the requirements doc.
