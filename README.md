# King of Kings: Phase 2 (Redis vs MySQL)

## Folder Directories
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
└── app/
    ├── config.py
    ├── generate_data.py
    ├── mysql_db.py
    ├── redis_db.py
    └── demo.py
```
---

## First-time setup (terminal)

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

### 5. Run the queries
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
---

## Everyday commands

What = Command

Start the databases = `docker compose up -d`
Stop them (keeps MySQL data) = `docker compose down`
Wipe everything and start over = `docker compose down -v`
Regenerate the CSVs = `docker compose run --rm app python -m app.generate_data`
Compare query runtimes = `docker compose run --rm app python -m app.demo`
See container logs = `docker compose logs mysql` / `docker compose logs redis`

---

## The dataset (for the report)

Source: [redis-developer/basic-redis-shopping-chart-nodejs](https://github.com/redis-developer/basic-redis-shopping-chart-nodejs) (MIT license), file `server/src/products.json`: 10 products with `id` (UUID), `name`, `price`, `stock`. A verbatim copy is in `data/source/products.json`.
 

**Table & Redis Conversion:**
| Table | Redis form |
| products | HASH `product:<id>` + STRING `stock:<id>` |
| price_history | TIME SERIES `price:<id>` (1 point/product/day, 2026-09-12 to 2026-11-10) |
| orders | STREAM `orders` |
| carts | SORTED SET `carts:updated` |
| cart_items | HASH `cart:<user_id>` |
| cart_seed | SORTED SET `cart_seed:age` |
| cart_seed_items | HASH `cart_seed:<user_id>` |


## The two queries

| | MySQL (`sql/queries.sql`) | Redis (`redis/queries.redis`) |
| **Query 1: Flash Sale** (feature-focused: key expiry) | Sale end time held in a session variable. A guarded `UPDATE ... WHERE stock >= 1 AND NOW() < @sale_ends` inside a transaction. No native expiry. | `SET flashsale:213 199.99 EX 60`. The key deletes itself. Stock is taken with an atomic `DECRBY`, or a one-command Lua `EVAL`. |
| **Query 2: Avg price per category per day, 60 days** (performance-focused: aggregation + join + range) | `JOIN products` to get each product's category, then `GROUP BY category, DATE(time)`. 360 rows. | `TS.MRANGE ... AGGREGATION avg 1 day ... GROUPBY category REDUCE avg`. The category is a label on each series, so no join. |
| **Query 2b: cheapest 20 in a category + price band** | `WHERE category=? AND price BETWEEN ? AND ? ORDER BY price LIMIT 20` on index `id_category_price` | `FT.SEARCH id:products "@category:{electronics} @price:[50 300]" SORTBY price LIMIT 0 20` |

---

## Versions (for the report's "software versions")

| Component | Version |
| MySQL | 8.4 (Docker image `mysql:8.4`) |
| Redis | 8.2 (Docker image `redis:8.2`, Search + Time Series built in) |
| Python | 3.12 (Docker image `python:3.12-slim`) |
| mysql-connector-python | 26.10.0 |
| redis (redis-py) | 8.1.0 |