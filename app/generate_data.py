"""
generate_data.py - builds every CSV in data/ from the GitHub sample dataset.

RUN IT
    python -m app.generate_data                 # default sizes (what we ship)
    python -m app.generate_data --products 100000 # 6 million price-history rows

You only need to run this if you want to CHANGE the dataset. The CSVs it
produces are already committed in data/, so a fresh clone can go straight to
loading.
"""

import argparse
import csv
import json
import random
import time
from datetime import datetime, timedelta

from app import config

# ---------------------------------------------------------------------------
# 1. Initial setup: random number generator, output folder, and CSV writer.
# ---------------------------------------------------------------------------
CATEGORY_FOR_GITHUB = {
    "Brilliant Watch": "fashion",
    "Old fashion cellphone": "electronics",
    "Modern iPhone": "electronics",
    "Beautiful Sunglasses": "fashion",
    "Stylish Cup": "home",
    "Herb caps": "health",          # the repo image is herbal capsules, not hats
    "Audiophile Headphones": "electronics",
    "Digital Camera": "electronics",
    "Empty Bluray Disc": "electronics",
    "256BG Pendrive": "electronics",  # name typo kept exactly as GitHub has it
}
GITHUB_BRAND = "RedisDemo"

# ---------------------------------------------------------------------------
# 2. Noun pool used to synthesize products 11..N.
# ---------------------------------------------------------------------------
NOUNS = [
    # electronics
    ("Cellphone",      "electronics",  24.00, "GitHub"),
    ("Smart Phone",    "electronics", 450.00, "Inventory list"),
    ("Headphones",     "electronics",  39.59, "Inventory list"),
    ("Digital Camera", "electronics", 225.00, "GitHub"),
    ("Bluray Disc",    "electronics",   5.00, "GitHub"),
    ("Pendrive",       "electronics",  60.00, "GitHub"),
    ("Speaker",        "electronics", 179.00, "Inventory list"),
    ("Laptop",         "electronics", 197.00, "Inventory list"),
    ("TV",             "electronics", 378.00, "Inventory list"),
    ("Charger",        "electronics", 290.82, "Redis Conversion tab example"),
    # fashion
    ("Watch",          "fashion",     250.00, "GitHub"),
    ("Sunglasses",     "fashion",      12.00, "GitHub"),
    ("Coat",           "fashion",      29.99, "Inventory list"),
    ("Dress",          "fashion",      42.59, "Inventory list"),
    ("Jeans",          "fashion",      19.38, "Inventory list"),
    ("Shoes",          "fashion",      25.00, "Inventory list"),
    # furniture
    ("Couch",          "furniture",   211.00, "Inventory list"),
    ("Table",          "furniture",    79.97, "Inventory list"),
    ("Chair",          "furniture",    59.99, "Inventory list"),
    ("Dresser",        "furniture",   148.00, "Inventory list"),
    # home / health (one GitHub item each)
    ("Cup",            "home",          8.00, "GitHub"),
    ("Herb Capsules",  "health",       12.00, "GitHub"),
    # auto
    ("Dash Cam",       "auto",         89.00, "placeholder"),
    ("Floor Mats",     "auto",         34.00, "placeholder"),
    ("Seat Cover",     "auto",         45.00, "placeholder"),
    ("Wiper Blades",   "auto",         19.00, "placeholder"),
]
BRANDS = ["Atlas", "Nova", "Summit", "Vertex", "Orion", "Apex", "Harbor", "Lumen", "Cobalt", "Zenith"]
STYLES = ["Classic", "Pro", "Lite", "Max", "Eco", "Ultra", "Prime", "Mini", "Plus", "Sport"]

# Product 213 is pinned to the exact example in our Redis Conversion tab
PINNED_PRODUCTS = {
    213: ("Atlas Classic Charger", "electronics", 290.82, "Atlas", 350),
}

DT_FORMAT = "%Y-%m-%d %H:%M:%S"   # MySQL DATETIME text format


def build_products(rng, n_products):
    """Return a list of product dicts with ids 1..n_products."""
    with open(config.SOURCE_DIR / "products.json", encoding="utf-8") as f:
        github_products = json.load(f)["products"]

    products = []
    # 2a. The 10 GitHub products, adapted (see module docstring).
    for new_id, item in enumerate(github_products, start=1):
        products.append({
            "id": new_id,
            "name": item["name"],
            "category": CATEGORY_FOR_GITHUB[item["name"]],
            "price": f'{float(item["price"]):.2f}',
            "brand": GITHUB_BRAND,
            "stock": int(item["stock"]),
        })

    # 2b. Synthetic products: random brand + style + noun, price within
    #     60%-160% of the noun's base price, random stock.
    for new_id in range(len(products) + 1, n_products + 1):
        if new_id in PINNED_PRODUCTS:
            name, category, price, brand, stock = PINNED_PRODUCTS[new_id]
        else:
            noun, category, base_price, _source = rng.choice(NOUNS)
            brand = rng.choice(BRANDS)
            name = f"{brand} {rng.choice(STYLES)} {noun}"
            price = max(1.00, round(base_price * rng.uniform(0.6, 1.6), 2))
            stock = rng.randint(5, 400)
        products.append({
            "id": new_id, "name": name, "category": category,
            "price": f"{price:.2f}", "brand": brand, "stock": stock,
        })
    return products


def build_price_history(rng, products):
    """Return a list of (product_id, time, price) tuples for the last 60 days."""
    days = [config.DATASET_LAST_DAY - timedelta(days=d) for d in range(config.HISTORY_DAYS)]
    rows = []
    for p in products:
        current = float(p["price"])
        price = current
        for day in days:   # newest -> oldest
            stamp = datetime(day.year, day.month, day.day, 12, 0, 0)
            rows.append((p["id"], stamp.strftime(DT_FORMAT), f"{price:.2f}"))
            # next (older) day's price: small random step, kept within +/-50%
            price = min(current * 1.5, max(current * 0.5, price * (1 + rng.gauss(0, 0.02))))
            price = max(0.50, round(price, 2))
    rows.sort(key=lambda r: (r[0], r[1]))   # product, then oldest -> newest
    return rows


def build_orders(rng, products, n_orders, n_users):
    """Random orders spread across the same 60-day window, ids in time order."""
    first_day = config.DATASET_LAST_DAY - timedelta(days=config.HISTORY_DAYS - 1)
    window_start = datetime(first_day.year, first_day.month, first_day.day)
    window_seconds = config.HISTORY_DAYS * 24 * 3600 - 1
    raw = []
    for _ in range(n_orders):
        created = window_start + timedelta(seconds=rng.randint(0, window_seconds))
        raw.append((rng.randint(1, n_users), rng.choice(products)["id"], rng.randint(1, 3), created))
    # Sorting by time BEFORE numbering means order id 1 is the oldest order.
    # Redis needs this: stream entry ids (XADD) must always increase.
    raw.sort(key=lambda r: r[3])
    return [(i, u, pid, qty, created.strftime(DT_FORMAT)) for i, (u, pid, qty, created) in enumerate(raw, start=1)]


def build_carts(rng, products, n_carts, n_users):
    """Return 4 lists: carts, cart_items, cart_seed, cart_seed_items. Each is a list of tuples ready to write to CSV."""
    now = datetime.combine(config.DATASET_LAST_DAY + timedelta(days=1), datetime.min.time())
    user_ids = sorted(rng.sample(range(1, n_users + 1), n_carts))
    carts, cart_items, seed, seed_items = [], [], [], []
    for uid in user_ids:
        age_min = rng.randint(1, 48 * 60)                 # touched within the last 48 hours
        updated_at = now - timedelta(minutes=age_min)
        carts.append((uid, updated_at.strftime(DT_FORMAT)))
        seed.append((uid, age_min))
        for p in rng.sample(products, rng.randint(1, 5)):  # 1-5 different products
            qty = rng.randint(1, 3)
            cart_items.append((uid, p["id"], qty))
            seed_items.append((uid, p["id"], qty))
    return carts, cart_items, seed, seed_items


def write_csv(filename, header, rows):
    path = config.DATA_DIR / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  wrote {filename:<22} {len(rows):>7,} rows")


def main():
    parser = argparse.ArgumentParser(description="Generate the project CSVs.")
    parser.add_argument(
        "--products", type=int, default=50000,
        help="number of products; price_history gets products x HISTORY_DAYS rows",
    )
    parser.add_argument("--orders", type=int, default=20000)
    parser.add_argument("--users", type=int, default=5000)
    parser.add_argument("--carts", type=int, default=3000)
    args = parser.parse_args()

    if args.products < max(PINNED_PRODUCTS):
        parser.error(f"--products must be at least {max(PINNED_PRODUCTS)}")
    if args.orders < 0 or args.users < 1 or args.carts < 0 or args.carts > args.users:
        parser.error("--orders and --carts must be non-negative, and --carts <= --users")

    rng = random.Random(config.RANDOM_SEED)
    started = time.perf_counter()
    print("Generating dataset ...")

    products = build_products(rng, args.products)
    columns = dict((table, cols) for table, _f, cols in config.TABLES)
    write_csv("products.csv", columns["products"],
              [(p["id"], p["name"], p["category"], p["price"], p["brand"], p["stock"]) for p in products])
    write_csv("price_history.csv", columns["price_history"], build_price_history(rng, products))
    write_csv("orders.csv", columns["orders"], build_orders(rng, products, args.orders, args.users))

    carts, cart_items, seed, seed_items = build_carts(rng, products, args.carts, args.users)
    write_csv("carts.csv", columns["carts"], carts)
    write_csv("cart_items.csv", columns["cart_items"], cart_items)
    write_csv("cart_seed.csv", columns["cart_seed"], seed)
    write_csv("cart_seed_items.csv", columns["cart_seed_items"], seed_items)

    print(f"Done in {time.perf_counter() - started:.2f}s -> {config.DATA_DIR}")


if __name__ == "__main__":
    main()
