# Ugefund

A small site that turns this week's Danish supermarket deals (Lidl, Føtex,
Netto, Rema 1000, 365discount) into quick dinner ideas.

## Files

- `index.html` — the whole site (plain HTML/JS, no build step)
- `deals.json` — this week's deals; overwritten automatically every Monday
- `scraper.py` — fetches current offers from the public Tjek/eTilbudsavis API
- `.github/workflows/update-deals.yml` — runs `scraper.py` on a weekly schedule
- `manifest.json`, `icon-192.png`, `icon-512.png` — lets the site be added to a phone home screen
- `scrape-log.txt` — created after the first scrape; check here if an update doesn't show up

## If the weekly scrape stops working

The scraper depends on an unofficial (but currently public, no-key-needed)
data feed. If a store renames itself, or the feed's shape changes, the
scraper is written to leave `deals.json` untouched rather than break the
site — check `scrape-log.txt` (or the Actions tab on GitHub) for what
happened, and hand the error to Claude to fix.
