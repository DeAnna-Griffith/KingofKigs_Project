"""
mysql_db.py - connect to MySQL, create the schema, load the CSVs.

RUN IT (from the project root)
------------------------------
    In Docker:      docker compose run --rm app python -m app.mysql_db
    In a terminal:  python -m app.mysql_db
"""

import csv
import time
import mysql.connector

from app import config

BATCH_SIZE = 5000


def get_connection(use_database=True):
    settings = dict(config.MYSQL)
    if not use_database:
        settings.pop("database")
    return mysql.connector.connect(**settings)


def read_sql_statements(path):
    lines = [line for line in path.read_text(encoding="utf-8").splitlines()
             if not line.strip().startswith("--")]
    return [stmt.strip() for stmt in "\n".join(lines).split(";") if stmt.strip()]


def apply_schema(conn):
    """Run every statement in sql/schema.sql (DROP + CREATE all tables)."""
    cursor = conn.cursor()
    for statement in read_sql_statements(config.SQL_DIR / "schema.sql"):
        cursor.execute(statement)
    conn.commit()
    cursor.close()


def load_table(conn, table, csv_file, columns):
    column_list = ", ".join(f"`{c}`" for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"

    started = time.perf_counter()
    cursor = conn.cursor()
    total = 0
    with open(config.DATA_DIR / csv_file, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        if header != columns:   # catches a CSV that no longer matches config.TABLES
            raise ValueError(f"{csv_file} header {header} != expected {columns}")
        batch = []
        for row in reader:
            batch.append(row)
            if len(batch) == BATCH_SIZE:
                cursor.executemany(sql, batch)
                total += len(batch)
                batch = []
        if batch:
            cursor.executemany(sql, batch)
            total += len(batch)
    conn.commit()
    cursor.close()
    return total, time.perf_counter() - started


def main():
    print(f"Connecting to MySQL at {config.MYSQL['host']}:{config.MYSQL['port']} ...")
    conn = get_connection(use_database=False)
    apply_schema(conn)       # creates database "shop" and all tables
    conn.database = config.MYSQL["database"]
    print("Schema applied (sql/schema.sql).\n")

    print(f"{'table':<18}{'rows':>10}{'seconds':>10}")
    grand_total = 0.0
    for table, csv_file, columns in config.TABLES:
        rows, seconds = load_table(conn, table, csv_file, columns)
        grand_total += seconds
        print(f"{table:<18}{rows:>10,}{seconds:>10.2f}")
    print(f"{'TOTAL':<18}{'':>10}{grand_total:>10.2f}\n")

    cursor = conn.cursor()
    for table, _, _ in config.TABLES:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  check: {table:<16} {cursor.fetchone()[0]:>8,} rows in MySQL")
    cursor.close()
    conn.close()
    print("\nMySQL is loaded.")


if __name__ == "__main__":
    main()
