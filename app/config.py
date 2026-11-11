"""
config.py - one place for every setting the other scripts share.
"""

import os
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"          # the CSV files live here
SOURCE_DIR = DATA_DIR / "source"          # copy of the GitHub dataset
SQL_DIR = PROJECT_ROOT / "sql"            # schema.sql + queries.sql
REDIS_DIR = PROJECT_ROOT / "redis"        # schema.redis + queries.redis

MYSQL = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "rootpass"),
    "database": os.getenv("MYSQL_DATABASE", "shop"),
}

REDIS = {
    "host": os.getenv("REDIS_HOST", "127.0.0.1"),
    "port": int(os.getenv("REDIS_PORT", "6379")),
    "decode_responses": True,
}


DATASET_LAST_DAY = date(2026, 11, 10)
HISTORY_DAYS = 60
RANDOM_SEED = 42   # same seed -> byte-for-byte identical CSVs every time

TABLES = [
    ("products",        "products.csv",        ["id", "name", "category", "price", "brand", "stock"]),
    ("orders",          "orders.csv",          ["id", "user_id", "product_id", "qty", "created_at"]),
    ("carts",           "carts.csv",           ["user_id", "updated_at"]),
    ("cart_items",      "cart_items.csv",      ["user_id", "product_id", "qty"]),
    ("price_history",   "price_history.csv",   ["product_id", "time", "price"]),
    ("cart_seed",       "cart_seed.csv",       ["user_id", "age_min"]),
    ("cart_seed_items", "cart_seed_items.csv", ["user_id", "product_id", "qty"]),
]
