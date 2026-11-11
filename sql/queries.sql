-- =============================================================================
-- queries.sql - our two Phase 2 queries, MySQL side
# RUN IT
#   grep -v '^--' queries.sql | mysql -u root -p shop | docker exec -i king-of-kings-phase2_mysql_1 mysql -u root -p shop
#   (For Windows) Get-Content sql/queries.sql | docker compose exec -T mysql mysql -uroot -prootpass --table shop

-- =============================================================================

USE shop;

-- =============================================================================
-- QUERY 1 - FLASH SALE | BUY ONE UNIT OF A PRODUCT AT A SPECIAL PRICE
-- =============================================================================

-- 1.0  Reset, so the query behaves the same every run.
UPDATE products SET stock = 350 WHERE id = 213;

-- 1.1  Open the sale window.  Redis twin: SET flashsale:213 199.99 EX 60
SET @product_id = 213;
SET @sale_price = 199.99;                         -- shown to shoppers; orders has no price column
SET @sale_ends  = NOW() + INTERVAL 60 SECOND;     -- the "EX 60" part

-- 1.2  Is the sale still live, and how long is left?
SELECT @product_id                                     AS product_id,
       @sale_price                                     AS sale_price,
       GREATEST(TIMESTAMPDIFF(SECOND, NOW(), @sale_ends), 0) AS seconds_left;

-- 1.3  ONE purchase attempt (the benchmark repeats this block per shopper).
--      The UPDATE does three things in one atomic statement:
--        - stock >= 1         -> never oversell
--        - NOW() < @sale_ends -> refuse after the window closes
--        - stock = stock - 1  -> take one unit
START TRANSACTION;
UPDATE products
   SET stock = stock - 1
 WHERE id = @product_id
   AND stock >= 1
   AND NOW() < @sale_ends;
SET @bought = ROW_COUNT();                        -- 1 = success, 0 = sold out or sale over

INSERT INTO orders (user_id, product_id, qty, created_at)
SELECT 42, @product_id, 1, NOW() FROM DUAL WHERE @bought = 1;
COMMIT;

SELECT @bought AS purchase_succeeded,
       (SELECT stock FROM products WHERE id = @product_id) AS stock_left;

-- 1.4  Simulate the window closing and try again: must be refused (0 rows).
SET @sale_ends = NOW() - INTERVAL 1 SECOND;
UPDATE products
   SET stock = stock - 1
 WHERE id = @product_id AND stock >= 1 AND NOW() < @sale_ends;
SELECT ROW_COUNT() AS purchase_after_sale_ended;


-- =============================================================================
-- QUERY 2 - AVERAGE PRICE PER CATEGORY PER DAY OVER 60 DAYS
-- =============================================================================

SET @first_day = '2026-09-12';
SET @last_day  = '2026-11-10';

SELECT p.category,
       DATE(ph.`time`)        AS day,
       ROUND(AVG(ph.price), 2) AS avg_price,
       COUNT(*)               AS prices_averaged
  FROM price_history AS ph
  JOIN products      AS p ON p.id = ph.product_id
 WHERE ph.`time` >= @first_day
   AND ph.`time` <  @last_day + INTERVAL 1 DAY    -- "< next midnight" includes all of the last day
 GROUP BY p.category, DATE(ph.`time`)
 ORDER BY p.category, day;


-- =============================================================================
-- QUERY 2b - CHEAPEST 20 PRODUCTS IN A CATEGORY AND PRICE BAND
-- =============================================================================

SELECT id, name, brand, price
  FROM products
 WHERE category = 'electronics'
   AND price BETWEEN 50 AND 300
 ORDER BY price ASC, id ASC
 LIMIT 20;

-- Proof the index is used: the "key" column should say id_category_price.
EXPLAIN
SELECT id, name, brand, price
  FROM products
 WHERE category = 'electronics' AND price BETWEEN 50 AND 300
 ORDER BY price ASC, id ASC
 LIMIT 20;
