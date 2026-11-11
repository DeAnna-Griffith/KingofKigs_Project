# King of Kings: Phase 2 (Redis vs MySQL)

## Project layout
```
king-of-kings-phase2/
├── README.md
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── data/
│   ├── source/products.json  the GitHub dataset
│   └── *.csv  one CSV per table (generated from the above)
├── sql/
│   ├── schema.sql
│   └── queries.sql
├── redis/
│   ├── schema.redis
│   └── queries.redis
├── app/
│   ├── config.py
│   ├── generate_data.py
│   ├── mysql_db.py
│   ├── redis_db.py
│   └── demo.py
├── testfiles/              <- optional Redis smoke checks
└── results/                <- timestamped benchmark CSVs
```
---

## Setup and run

You need: [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running. That's all for the Docker route. Run every command from inside the project folder.

### 1. Go to the project folder
```bash
cd king-of-kings-phase2
```

### 2. Start MySQL and Redis
```bash
docker compose up -d
```

The first run downloads the images, which takes a few minutes. Then check that both are ready:
```bash
docker compose ps
```
Wait until both rows say **`(healthy)`**.

### 3. Load the data into MySQL
```bash
docker compose run --rm app python -m app.mysql_db
```

### 4. Load the same data into Redis
```bash
docker compose run --rm app python -m app.redis_db
```

### 5. Run the queries manually (optional)
```bash
docker compose exec -T mysql mysql -uroot -prootpass --table shop < sql/queries.sql
```

Redis, whole file. `redis-cli` doesn't understand `#` comments, so `grep` strips them first:
```bash
grep -v '^#' redis/queries.redis | docker compose exec -T redis redis-cli
```

```bash
docker compose exec mysql mysql -uroot -prootpass shop     # MySQL prompt (type exit to leave)
docker compose exec redis redis-cli                        # Redis prompt (type exit to leave)
```

> MySQL prints `Using a password on the command line interface can be insecure`. That's harmless here.

### Windows (PowerShell) versions of step 5

PowerShell has no `<` redirect or `grep`, so use these:

```powershell
Get-Content sql/queries.sql | docker compose exec -T mysql mysql -uroot -prootpass --table shop
Get-Content redis/queries.redis | Where-Object { $_ -notmatch '^#' } | docker compose exec -T redis redis-cli
```

### 6. Compare query runtimes

```bash
docker compose run --rm app python -m app.demo
```

The benchmark runs the same 60-day price-history aggregation against both
databases. It performs one untimed warmup and five timed runs per database by
default, fetches and normalizes the complete result in each run, checks that
both systems return the same category/day buckets and near-equal averages, and
prints each runtime plus the average and median. Timings include query
execution, response transfer, and client-side result decoding, but exclude
connection setup.

Each run is saved to a new CSV under `results/`, including individual samples
and summary rows. To choose the sample size:

```bash
docker compose run --rm app python -m app.demo --runs 10 --warmups 2
```

An alternate CSV path can be supplied with `--output results/my_run.csv`.
Only Query 2 is benchmarked: Query 1 mutates inventory and orders, while
Query 2b is an optional indexed search with a much smaller result set. Do not
compare timings from different machines or database configurations as if they
were a controlled experiment.

The optional Redis smoke checks can be run with
`docker compose run --rm app python -m testfiles.test` and
`docker compose run --rm app python -m testfiles.test2`. The second check
expects the product search index to have been loaded.

---

## Option B: run the Python on your machine instead of in Docker

The databases still run in Docker (step 2). Only the Python scripts run locally. You need Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m app.mysql_db
python -m app.redis_db
```

The Compose file publishes MySQL on host port `3307`; the local Python
configuration uses that port by default. Inside Compose, the app connects to
MySQL on its internal port `3306`.
---

## Everyday commands

| What | Command |
|---|---|
| Start the databases | `docker compose up -d` |
| Stop them (keeps MySQL data) | `docker compose down` |
| Wipe everything and start over | `docker compose down -v` |
| Regenerate the default 50,000-product CSV dataset | `docker compose run --rm app python -m app.generate_data` |
| Compare query runtimes | `docker compose run --rm app python -m app.demo` |
| See container logs | `docker compose logs mysql` / `docker compose logs redis` |

---

## The dataset (for the report)

**Source:** [redis-developer/basic-redis-shopping-chart-nodejs](https://github.com/redis-developer/basic-redis-shopping-chart-nodejs) (MIT license), `server/src/products.json`, containing 10 products. A copy is in `data/source/products.json`. The remaining records are synthetic and generated deterministically from the source products and the fixed random seed.

The shipped CSVs contain 50,000 products and 3,000,000 daily price-history records spanning 2026-09-12 through 2026-11-10. Regenerate with `python -m app.generate_data`; use `--products`, `--orders`, `--users`, and `--carts` to select a different workload. Reload both databases after regenerating the CSVs.

| Table | Rows | Redis representation |
|---|---:|---|
| products | 50,000 | HASH `product:<id>` + STRING `stock:<id>` |
| price_history | 3,000,000 | TIME SERIES `price:<id>` |
| orders | 20,000 | STREAM `orders` |
| carts | 3,000 | SORTED SET `carts:updated` |
| cart_items | 9,083 | HASH `cart:<user_id>` |
| cart_seed | 3,000 | SORTED SET `cart_seed:age` |
| cart_seed_items | 9,083 | HASH `cart_seed:<user_id>` |
| **Total** | **3,094,166** | **156,003 keys plus the `id:products` search index** |


## The two queries

| Query | MySQL | Redis |
|---|---|---|
| **1. Flash sale** (feature demonstration) | Keeps an expiry time in a session variable and uses a guarded stock update in a transaction. MySQL has no native expiring row. | An expiring sale key plus a Lua script that checks sale/stock and atomically decrements stock and appends the order. |
| **2. Daily average price per category** (timed workload) | Joins `price_history` to `products`, groups by category and day, and averages all prices in the 60-day range. Returns 360 rows. | `TS.MRANGE` aggregates daily and reduces by the category label on each series. Returns the same 360 category/day buckets without a join. |
| **2b. Cheapest 20 in a category and price band** (optional) | Filters and sorts `products` using the category/price index. | `FT.SEARCH` applies matching tag and numeric filters and returns the first 20 by price; equal-price ties may return in a different order. |

Query 2 is the apples-to-apples performance comparison implemented by the
benchmark. Query 1 is stateful and is intended to demonstrate expiry and
atomicity, not to serve as a repeatable read-query timing.

## Benchmark report

### Experimental setup

- One Windows host with an AMD Ryzen 5 7530U processor and 7.3 GiB of RAM.
- MySQL and Redis ran in Docker; the Python benchmark ran in the Python 3.12 app container.
- Dataset: 50,000 products and 3,000,000 price-history points over 60 days.
- The benchmark performed one untimed warmup and five timed runs per database, alternating which database ran first. Timings use `time.perf_counter()` and include fetching the complete result, but not connection setup.
- Both systems returned the same 360 category/day buckets. Their averages were checked to within 0.011 to accommodate MySQL decimal rounding and Redis floating-point aggregation.

### Performance results

Observed on 2026-11-11; individual times are seconds:

| Database | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Average | Median |
|---|---:|---:|---:|---:|---:|---:|---:|
| MySQL | 2.6096 | 2.4186 | 2.4425 | 2.4384 | 2.6473 | 2.5113 | 2.4425 |
| Redis | 1.1942 | 0.9938 | 1.0608 | 0.9900 | 1.0184 | 1.0515 | 1.0184 |

Redis was about 2.39x faster in this run, with an average difference of
1.4598 seconds. Raw observations and summaries are in
[`results/benchmark_results_20261111T153402Z.csv`](results/benchmark_results_20261111T153402Z.csv).

### Analysis and interpretation

Redis was faster for this particular workload and setup. Its time-series
labels carry the product category, so the query avoids MySQL's relational join
and uses time-series aggregation/reduction. The result is specific to this
machine, dataset, software versions, Docker resource allocation, and run
conditions; five samples are a useful demonstration, not a universal ranking
or a statistical guarantee.

### Challenges encountered

- The SQL files were nested one directory too deep for the app and Docker
  configuration. They now live directly under `sql/`.
- The two clients return aggregation results in different shapes and numeric
  formats. The benchmark normalizes category/day buckets and verifies matching
  results before recording the timings.
- Redis averages are floating point while MySQL returns rounded decimals, so
  the value comparison uses a small documented tolerance.
- The 3-million-row data set is large enough to expose workload timing
  differences, but is costly to load and store. The generator now streams
  price-history records in sorted order instead of retaining the full history
  in memory.

---

## Versions (for the report's "software versions")

| Component | Version |
|---|---|
| MySQL | 8.4.13 (Docker image `mysql:8.4`) |
| Redis | 8.2.11 (Docker image `redis:8.2`, Search + Time Series built in) |
| Python | 3.12.16 (Docker image `python:3.12-slim`) |
| mysql-connector-python | 26.10.0 |
| redis (redis-py) | 8.1.0 |

For a new report run, record the host CPU and available memory along with the
new benchmark CSV; results depend on that environment.