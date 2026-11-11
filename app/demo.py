"""
Benchmark the matching 60-day price-history aggregation in MySQL and Redis.

Run after loading both databases:
    python -m app.demo
    python -m app.demo --runs 10 --warmups 2
"""

import argparse
import csv
import shlex
import statistics
import time
from datetime import datetime, time as datetime_time, timedelta, timezone
from pathlib import Path

from app import config
from app.mysql_db import (
    get_connection as get_mysql_connection,
    read_sql_statements,
)
from app.redis_db import get_connection as get_redis_connection


OUTPUT_FIELDS = [
    "record_type",
    "run_id",
    "recorded_at_utc",
    "query",
    "database",
    "run_number",
    "elapsed_seconds",
    "result_count",
    "average_seconds",
    "median_seconds",
]
RESULT_TOLERANCE = 0.011


def query_window():
    """Return matching inclusive-start/exclusive-end bounds for both stores."""
    first_day = config.DATASET_LAST_DAY - timedelta(days=config.HISTORY_DAYS - 1)
    last_day_exclusive = config.DATASET_LAST_DAY + timedelta(days=1)
    start = datetime.combine(first_day, datetime_time.min)
    end = datetime.combine(last_day_exclusive, datetime_time.min)
    start_ms = int(start.replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = int(end.replace(tzinfo=timezone.utc).timestamp() * 1000) - 1
    return start, end, start_ms, end_ms


def load_mysql_query():
    statements = read_sql_statements(config.SQL_DIR / "queries.sql")
    for statement in statements:
        normalized = " ".join(statement.upper().split())
        if normalized.startswith("SELECT P.CATEGORY") and "PRICE_HISTORY AS PH" in normalized:
            return statement
    raise RuntimeError("Could not find the category/day aggregation in sql/queries.sql")


def load_redis_query(start_ms, end_ms):
    for line in (config.REDIS_DIR / "queries.redis").read_text(
        encoding="utf-8"
    ).splitlines():
        line = line.strip()
        if line.startswith("TS.MRANGE "):
            command = shlex.split(line)
            return [command[0], start_ms, end_ms, *command[3:]]
    raise RuntimeError("Could not find TS.MRANGE in redis/queries.redis")


def run_mysql_query(connection, query):
    cursor = connection.cursor()
    try:
        cursor.execute(query)
        return {
            (category, day): (float(avg_price), int(row_count))
            for category, day, avg_price, row_count in cursor.fetchall()
        }
    finally:
        cursor.close()


def run_redis_query(connection, query):
    response = connection.execute_command(*query)
    results = {}
    for group_name, group in response.items():
        if not group or not isinstance(group[-1], list):
            raise RuntimeError(f"Unexpected Redis time-series response for {group_name!r}")
        category = group_name.removeprefix("category=")
        for timestamp, average in group[-1]:
            day = datetime.fromtimestamp(
                int(timestamp) / 1000, tz=timezone.utc
            ).date()
            results[(category, day)] = float(average)
    return results


def timed_query(query):
    started = time.perf_counter()
    result = query()
    return time.perf_counter() - started, result


def compare_results(mysql_results, redis_results):
    if mysql_results.keys() != redis_results.keys():
        missing_in_redis = sorted(mysql_results.keys() - redis_results.keys())[:5]
        missing_in_mysql = sorted(redis_results.keys() - mysql_results.keys())[:5]
        raise RuntimeError(
            "MySQL and Redis returned different category/day buckets. "
            f"Missing in Redis: {missing_in_redis}; missing in MySQL: {missing_in_mysql}"
        )

    for key, mysql_result in mysql_results.items():
        mysql_average = mysql_result[0]
        redis_average = redis_results[key]
        if abs(mysql_average - redis_average) > RESULT_TOLERANCE:
            raise RuntimeError(
                f"Average mismatch for {key}: MySQL={mysql_average}, Redis={redis_average}"
            )


def write_results(path, run_id, recorded_at, durations, result_count):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for database, values in durations.items():
            for run_number, elapsed in enumerate(values, start=1):
                writer.writerow({
                    "record_type": "run",
                    "run_id": run_id,
                    "recorded_at_utc": recorded_at,
                    "query": "daily_category_average",
                    "database": database,
                    "run_number": run_number,
                    "elapsed_seconds": f"{elapsed:.6f}",
                    "result_count": result_count,
                    "average_seconds": "",
                    "median_seconds": "",
                })
            writer.writerow({
                "record_type": "summary",
                "run_id": run_id,
                "recorded_at_utc": recorded_at,
                "query": "daily_category_average",
                "database": database,
                "run_number": "",
                "elapsed_seconds": "",
                "result_count": result_count,
                "average_seconds": f"{statistics.mean(values):.6f}",
                "median_seconds": f"{statistics.median(values):.6f}",
            })


def main():
    parser = argparse.ArgumentParser(
        description="Compare MySQL and Redis on the daily price aggregation query."
    )
    parser.add_argument("--runs", type=int, default=5, help="timed runs per database")
    parser.add_argument("--warmups", type=int, default=1, help="untimed runs per database")
    parser.add_argument(
        "--output",
        type=Path,
        help="CSV output path (default: results/benchmark_results_<UTC timestamp>.csv)",
    )
    args = parser.parse_args()
    if args.runs < 1 or args.warmups < 0:
        parser.error("--runs must be at least 1 and --warmups cannot be negative")

    mysql = None
    redis_client = None
    try:
        mysql = get_mysql_connection()
        redis_client = get_redis_connection()
        redis_client.ping()
        start, end, start_ms, end_ms = query_window()
        cursor = mysql.cursor()
        try:
            cursor.execute("SET @first_day = %s", (start.date(),))
            cursor.execute("SET @last_day = %s", (end.date() - timedelta(days=1),))
        finally:
            cursor.close()

        mysql_statement = load_mysql_query()
        redis_command = load_redis_query(start_ms, end_ms)
        mysql_query = lambda: run_mysql_query(mysql, mysql_statement)
        redis_query = lambda: run_redis_query(redis_client, redis_command)

        print("Warming up both databases...")
        for _ in range(args.warmups):
            mysql_query()
            redis_query()

        timings = {"MySQL": [], "Redis": []}
        last_results = {}
        queries = {"MySQL": mysql_query, "Redis": redis_query}
        for run_number in range(args.runs):
            order = ("MySQL", "Redis") if run_number % 2 == 0 else ("Redis", "MySQL")
            for database in order:
                elapsed, result = timed_query(queries[database])
                timings[database].append(elapsed)
                last_results[database] = result

        compare_results(last_results["MySQL"], last_results["Redis"])
        result_count = len(last_results["MySQL"])
        if not result_count:
            raise RuntimeError("The queries returned no results; verify that both databases are loaded")

        now = datetime.now(timezone.utc)
        recorded_at = now.isoformat(timespec="seconds")
        run_id = now.strftime("%Y%m%dT%H%M%SZ")
        output_path = args.output or (
            config.PROJECT_ROOT / "results" / f"benchmark_results_{run_id}.csv"
        )
        if not output_path.is_absolute():
            output_path = config.PROJECT_ROOT / output_path
        write_results(output_path, run_id, recorded_at, timings, result_count)

        print("\nQuery: average price per category per day over the configured date range")
        print(f"Result buckets: {result_count:,}")
        print(f"Timed runs per database: {args.runs}; warmups: {args.warmups}")
        print("\nDatabase  Individual runs (seconds)                         Average    Median")
        for database, values in timings.items():
            individual = ", ".join(f"{value:.4f}" for value in values)
            print(
                f"{database:<9} {individual:<48} "
                f"{statistics.mean(values):>8.4f}  {statistics.median(values):>8.4f}"
            )

        mysql_average = statistics.mean(timings["MySQL"])
        redis_average = statistics.mean(timings["Redis"])
        print(f"\nAverage difference: {abs(mysql_average - redis_average):.4f}s")
        if mysql_average and redis_average:
            ratio = max(mysql_average, redis_average) / min(mysql_average, redis_average)
            faster = "MySQL" if mysql_average < redis_average else "Redis"
            print(f"Average speed ratio: {ratio:.2f}x ({faster} faster)")
        print(f"Results saved to: {output_path}")
    finally:
        if mysql is not None:
            mysql.close()
        if redis_client is not None:
            redis_client.close()


if __name__ == "__main__":
    main()
