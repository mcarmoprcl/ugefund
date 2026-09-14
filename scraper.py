"""
Weekly deal scraper for Ugefund.

Pulls current offers for Lidl, Føtex, Netto, Rema 1000 and 365discount from
the public Tjek / eTilbudsavis API (the data feed behind etilbudsavis.dk,
which many Danish pamphlet sites and apps run on) and writes them to
deals.json in the format the website reads.

No API key required. If anything goes wrong (network hiccup, API shape
change, a store renamed), this script leaves the existing deals.json
untouched rather than overwriting it with something broken, and appends
a line to scrape-log.txt explaining what happened — check that file first
if a weekly update doesn't show up.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = "https://api.etilbudsavis.dk/v2"
HERE = Path(__file__).parent
DEALS_FILE = HERE / "deals.json"
LOG_FILE = HERE / "scrape-log.txt"

STORE_MATCHERS = {
    "lidl": ["lidl"],
    "foetex": ["føtex", "foetex", "fotex"],
    "netto": ["netto"],
    "rema": ["rema 1000", "rema1000", "rema"],
    "365": ["365discount", "365 discount"],
}

CATEGORY_KEYWORDS = {
    "Kød & fisk": [
        "kød", "kylling", "oksekød", "svinekød", "laks", "rejer", "fisk",
        "bacon", "pølse", "farsbrød", "frikadelle", "torsk", "skinke",
    ],
    "Mejeri": ["mælk", "ost", "yoghurt", "fløde", "smør", "æg", "skyr", "kvark"],
    "Frugt & grønt": [
        "banan", "æble", "tomat", "agurk", "kartof", "løg", "frugt",
        "grønt", "salat", "peber", "gulerod", "citron", "avocado",
    ],
    "Drikkevarer": [
        "sodavand", "øl", "juice", "saft", "vand", "cola", "most", "vin",
        "cider", "energidrik", "kaffe", "te ", "drik", "danskvand",
        "kildevand", "mineralvand", "saftevand", "smoothie", "proteindrik",
        "isvand", "tonic", "spiritus", "snaps", "akvavit", "whisky", "rom ",
        "vodka", "gin ", "pilsner", "guldøl", "julebryg", "alkoholfri",
    ],
    "Slik & chokolade": [
        "slik", "chokolade", "bolsje", "tyggegummi", "lakrids", "vingummi",
        "kiks", "småkage", "is ", "dessert", "flødebolle", "skumfidus",
        "marshmallow", "påskeæg", "juleslik", "bland selv", "fudge",
        "nougat", "praliner", "guf", "vaniljeis", "softice",
    ],
    "Rengøring & hygiejne": [
        "rengøring", "vaskemiddel", "opvask", "toiletpapir", "shampoo",
        "sæbe", "tandpasta", "hygiejne", "affaldspose", "køkkenrulle",
        "ble", "servietter", "rens", "vasketabs", "skyllemiddel", "wc ",
        "vinduespudser", "klud", "svamp", "håndsæbe", "deodorant",
        "hårspray", "hårfarve", "solcreme", "plaster", "barberskum",
        "hygiejnebind", "tamponer",
    ],
}

WORD_TRANSLATIONS = {
    "hakket": "ground", "oksekød": "beef", "svinekød": "pork",
    "kyllingefileter": "chicken fillets", "kylling": "chicken", "kyllingebryst": "chicken breast",
    "laksefileter": "salmon fillets", "laks": "salmon", "torsk": "cod", "fisk": "fish",
    "rejer": "shrimp", "frosne": "frozen", "frisk": "fresh", "friske": "fresh",
    "bacon": "bacon", "pølser": "sausages", "pølse": "sausage", "skinke": "ham",
    "frikadeller": "meatballs", "farsbrød": "meatloaf",
    "bananer": "bananas", "banan": "banana", "æbler": "apples", "æble": "apple",
    "tomater": "tomatoes", "tomat": "tomato", "agurk": "cucumber", "agurker": "cucumbers",
    "kartofler": "potatoes", "kartoffel": "potato", "løg": "onions", "gulerødder": "carrots",
    "gulerod": "carrot", "salat": "lettuce", "peberfrugt": "bell pepper", "avocado": "avocado",
    "citron": "lemon", "citroner": "lemons", "appelsin": "orange", "appelsiner": "oranges",
    "druer": "grapes", "jordbær": "strawberries", "champignon": "mushrooms", "champignoner": "mushrooms",
    "æg": "eggs", "mælk": "milk", "sødmælk": "whole milk", "minimælk": "low-fat milk",
    "ost": "cheese", "flødeost": "cream cheese", "smør": "butter", "smørbar": "spreadable butter",
    "yoghurt": "yoghurt", "skyr": "skyr", "kvark": "quark", "fløde": "cream", "piskefløde": "whipping cream",
    "rugbrød": "rye bread", "toastbrød": "sandwich bread", "brød": "bread", "boller": "buns",
    "franskbrød": "white bread", "pasta": "pasta", "ris": "rice", "mel": "flour", "sukker": "sugar",
    "naturel": "plain", "øko": "organic", "økologisk": "organic", "stk": "pcs", "net": "net bag",
    "sodavand": "soda", "øl": "beer", "juice": "juice", "saft": "squash", "vand": "water",
    "danskvand": "sparkling water", "cola": "cola", "most": "juice", "vin": "wine", "cider": "cider",
    "energidrik": "energy drink", "kaffe": "coffee", "te": "tea",
    "slik": "candy", "chokolade": "chocolate", "bolsjer": "boiled sweets", "tyggegummi": "chewing gum",
    "lakrids": "liquorice", "vingummi": "gummy sweets", "kiks": "biscuits", "småkager": "cookies",
    "is": "ice cream",
    "rengøringsmiddel": "cleaning product", "vaskemiddel": "laundry detergent", "opvaskemiddel": "dish soap",
    "toiletpapir": "toilet paper", "shampoo": "shampoo", "sæbe": "soap", "tandpasta": "toothpaste",
    "affaldsposer": "trash bags", "køkkenrulle": "paper towels", "bleer": "diapers", "servietter": "napkins",
    "rens": "cleaner", "skyllemiddel": "fabric softener",
    "eller": "or", "og": "and", "med": "with", "uden": "without", "ca": "approx.",
    "stor": "large", "store": "large", "lille": "small", "små": "small",
    "blandet": "mixed", "blandede": "mixed", "udvalgte": "selected", "diverse": "assorted",
    "hel": "whole", "halv": "half", "let": "light", "fed": "full-fat", "mager": "lean",
    "danske": "danish", "dansk": "danish", "importeret": "imported",
}


def translate_best_effort(heading: str) -> str:
    words = heading.split(" ")
    out = []
    for w in words:
        core = re.sub(r"[^\wæøå%-]", "", w.lower())
        translated = WORD_TRANSLATIONS.get(core)
        out.append(translated if translated else w)
    return " ".join(out)


def categorize(heading: str) -> str:
    low = heading.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(k in low for k in keywords):
            return category
    return "Kolonial"


def log(message: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {message}\n")
    print(message)


def fetch_dealers() -> list[dict]:
    dealers = []
    offset = 0
    page_size = 100
    while True:
        resp = requests.get(
            f"{BASE_URL}/dealers",
            params={"country_id": "DK", "limit": page_size, "offset": offset},
            timeout=20,
        )
        resp.raise_for_status()
        batch = resp.json()
        dealers.extend(batch)
        if len(batch) < page_size or offset > 3000:
            break
        offset += page_size
    return dealers


def match_dealer_ids(dealers: list[dict]) -> tuple[dict, dict, dict]:
    matched = {}
    logos = {}
    links = {}
    for dealer in dealers:
        name_low = (dealer.get("name") or "").lower()
        for our_id, needles in STORE_MATCHERS.items():
            if our_id in matched:
                continue
            if any(needle in name_low for needle in needles):
                matched[our_id] = dealer["id"]
                if dealer.get("logo"):
                    logos[our_id] = dealer["logo"]
                if dealer.get("website"):
                    links[our_id] = dealer["website"]
    return matched, logos, links


def fetch_offers(dealer_id: str) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/offers", params={"dealer_id": dealer_id, "limit": 50}, timeout=20
    )
    resp.raise_for_status()
    return resp.json()


def raw_qty(raw: dict) -> dict:
    qty = raw.get("quantity") or {}
    size = (qty.get("size") or {}).get("from")
    unit = (qty.get("unit") or {}).get("symbol")
    pieces = (qty.get("pieces") or {}).get("from")
    return {"size": size, "unit": unit, "pieces": pieces}


def unit_label(raw: dict) -> str:
    q = raw_qty(raw)
    if q["size"] and q["unit"]:
        return f"{q['size']:g} {q['unit']}"
    if q["pieces"]:
        return f"{q['pieces']:g} pcs"
    return ""


def build_deals() -> tuple[list[dict], dict, dict]:
    dealers = fetch_dealers()
    log(f"Dealers returned by API ({len(dealers)}): " + ", ".join(sorted(d.get("name", "?") for d in dealers)))

    dealer_ids, store_logos, store_links = match_dealer_ids(dealers)

    missing = [s for s in STORE_MATCHERS if s not in dealer_ids]
    if missing:
        log(f"Warning: couldn't find a dealer match for: {', '.join(missing)}")

    deals = []
    next_id = 1
    for our_store_id, dealer_id in dealer_ids.items():
        try:
            offers = fetch_offers(dealer_id)
        except requests.RequestException as e:
            log(f"Warning: failed to fetch offers for {our_store_id}: {e}")
            continue

        kept = 0
        for raw in offers:
            pricing = raw.get("pricing") or {}
            price = pricing.get("price")
            was = pricing.get("pre_price")
            heading = raw.get("heading")

            if not heading or price is None:
                continue
            if was is not None and was <= price:
                was = None

            deals.append(
                {
                    "id": next_id,
                    "store": our_store_id,
                    "category": categorize(heading),
                    "name": heading,
                    "nameEn": translate_best_effort(heading),
                    "unit": unit_label(raw),
                    "qty": raw_qty(raw),
                    "validUntil": raw.get("run_till"),
                    "price": round(float(price), 2),
                    "was": round(float(was), 2) if was is not None else None,
                    "image": (raw.get("images") or {}).get("view"),
                }
            )
            next_id += 1
            kept += 1

        log(f"{our_store_id}: fetched {len(offers)} raw offers, kept {kept} with a usable price.")
        if offers and kept == 0:
            sample = [
                {"heading": o.get("heading"), "pricing": o.get("pricing"), "quantity": o.get("quantity")}
                for o in offers[:2]
            ]
            log(f"{our_store_id}: sample raw offer(s) for debugging: {json.dumps(sample, ensure_ascii=False)}")

    return deals, store_logos, store_links


def main() -> int:
    try:
        deals, store_logos, store_links = build_deals()
    except requests.RequestException as e:
        log(f"Scrape failed (network/API error), keeping existing deals.json: {e}")
        return 0
    except Exception as e:
        log(f"Scrape failed (unexpected error), keeping existing deals.json: {e}")
        return 0

    if not deals:
        log("Scrape returned zero deals — keeping existing deals.json to be safe.")
        return 0

    payload = {
        "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "storeLogos": store_logos,
        "storeLinks": store_links,
        "deals": deals,
    }
    DEALS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Success: wrote {len(deals)} deals across {len(set(d['store'] for d in deals))} stores.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
