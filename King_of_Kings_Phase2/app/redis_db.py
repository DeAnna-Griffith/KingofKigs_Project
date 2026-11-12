"""
redis_db.py - connect to Redis, declare the index, load the CSVs.

RUN IT (from the project root)
------------------------------
    In Docker:      docker compose run --rm app python -m app.redis_db
    In a terminal:  python -m app.redis_db
"""

import csv
import shlex
import time
from datetime import datetime, timezone

import redis   # the official Python client ("redis" on PyPI, a.k.a. redis-py)

from app import config

BATCH_SIZE = 5000
INDEX_NAME = "id:products"


def get_connection():
    return redis.Redis(**config.REDIS)


# Helpers
def read_csv(csv_file):
    """Yield each CSV row as a dict, e.g. {"id": "213", "name": "...", ...}."""
    with open(config.DATA_DIR / csv_file, newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def to_epoch_ms(text):
    """'2026-11-10 12:00:00' -> 1794312000000 (unix ms, read as UTC).
    Time series and stream ids are numbers, not date strings."""
    dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def run_in_batches(r, rows, add_commands):
    pipe = r.pipeline(transaction=False)
    count = 0
    for row in rows:
        add_commands(pipe, row)
        count += 1
        if count % BATCH_SIZE == 0:
            pipe.execute()          # send this batch, wait for the replies
    pipe.execute()                  # send whatever is left
    return count


# Step 1 + 2: reset and declare the index.
def reset(r):
    """Drop the search index (if it exists) and delete every key."""
    try:
        r.execute_command("FT.DROPINDEX", INDEX_NAME)
    except redis.ResponseError as exc:
        if "Unknown Index name" not in str(exc):
            raise
    r.flushdb()


def apply_schema(r):
    for line in (config.REDIS_DIR / "schema.redis").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            r.execute_command(*shlex.split(line))


# Step 3: one loader per MySQL table.
def load_products(r):
    """products -> HASH product:<id> + STRING stock:<id>"""
    def commands(pipe, row):
        pipe.hset(f"product:{row['id']}", mapping={
            "name": row["name"],
            "category": row["category"],
            "brand": row["brand"],
            "price": row["price"],
        })
        pipe.set(f"stock:{row['id']}", row["stock"])
    return run_in_batches(r, read_csv("products.csv"), commands)


def load_price_history(r):
    category_of = {row["id"]: row["category"] for row in read_csv("products.csv")}

    pipe = r.pipeline(transaction=False)
    for product_id, category in category_of.items():
        pipe.execute_command(
            "TS.CREATE", f"price:{product_id}",
            "DUPLICATE_POLICY", "LAST",
            "LABELS", "kind", "price", "category", category, "product", product_id,
        )
    pipe.execute()

    def commands(pipe, row):
        pipe.execute_command("TS.ADD", f"price:{row['product_id']}",
                             to_epoch_ms(row["time"]), row["price"])
    return run_in_batches(r, read_csv("price_history.csv"), commands)


def load_orders(r):
    def commands(pipe, row):
        pipe.xadd("orders", {
            "order_id": row["id"],
            "user_id": row["user_id"],
            "product_id": row["product_id"],
            "qty": row["qty"],
        }, id=f"{to_epoch_ms(row['created_at'])}-*")
    return run_in_batches(r, read_csv("orders.csv"), commands)


def load_carts(r):
    def commands(pipe, row):
        pipe.zadd("carts:updated", {row["user_id"]: to_epoch_ms(row["updated_at"]) // 1000})
    return run_in_batches(r, read_csv("carts.csv"), commands)


def load_cart_items(r):
    def commands(pipe, row):
        pipe.hset(f"cart:{row['user_id']}", f"product:{row['product_id']}", row["qty"])
    return run_in_batches(r, read_csv("cart_items.csv"), commands)


def load_cart_seed(r):
    def commands(pipe, row):
        pipe.zadd("cart_seed:age", {row["user_id"]: int(row["age_min"])})
    return run_in_batches(r, read_csv("cart_seed.csv"), commands)


def load_cart_seed_items(r):
    def commands(pipe, row):
        pipe.hset(f"cart_seed:{row['user_id']}", f"product:{row['product_id']}", row["qty"])
    return run_in_batches(r, read_csv("cart_seed_items.csv"), commands)

LOADERS = {
    "products": load_products,
    "orders": load_orders,
    "carts": load_carts,
    "cart_items": load_cart_items,
    "price_history": load_price_history,
    "cart_seed": load_cart_seed,
    "cart_seed_items": load_cart_seed_items,
}


def main():
    print(f"Connecting to Redis at {config.REDIS['host']}:{config.REDIS['port']} ...")
    r = get_connection()
    print(f"Redis server version {r.info('server')['redis_version']}")
    reset(r)
    apply_schema(r)
    print("Database reset and schema applied (redis/schema.redis).\n")

    print(f"{'table':<18}{'rows':>10}{'seconds':>10}")
    grand_total = 0.0
    for table, _, _ in config.TABLES:
        started = time.perf_counter()
        rows = LOADERS[table](r)
        seconds = time.perf_counter() - started
        grand_total += seconds
        print(f"{table:<18}{rows:>10,}{seconds:>10.2f}")
    print(f"{'TOTAL':<18}{'':>10}{grand_total:>10.2f}\n")

    # Verify with Redis's own commands.
    info = r.ft(INDEX_NAME).info()
    print(f"  check: products indexed by {INDEX_NAME}: {info['num_docs']}")
    print(f"  check: price time series (kind=price): {len(r.execute_command('TS.QUERYINDEX', 'kind=price')):,}")
    print(f"  check: entries in orders stream:       {r.xlen('orders'):,}")
    print(f"  check: carts in carts:updated:         {r.zcard('carts:updated'):,}")
    print(f"  check: total keys (DBSIZE):            {r.dbsize():,}")
    print("\nRedis is loaded.")


if __name__ == "__main__":
    main()
