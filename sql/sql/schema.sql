-- =============================================================================
-- schema.sql - MySQL schema for the King of Kings Phase 2 project
-- =============================================================================

CREATE DATABASE IF NOT EXISTS shop
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE shop;


DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS cart_items;
DROP TABLE IF EXISTS carts;
DROP TABLE IF EXISTS price_history;
DROP TABLE IF EXISTS cart_seed_items;
DROP TABLE IF EXISTS cart_seed;
DROP TABLE IF EXISTS products;

-- -----------------------------------------------------------------------------
-- products - catalog & inventory
-- -----------------------------------------------------------------------------
CREATE TABLE products (
  id        INT            NOT NULL,
  name      VARCHAR(120)   NOT NULL,
  category  VARCHAR(40)    NOT NULL, -- electronics, fashion, furniture, home, health, auto
  price     DECIMAL(10,2)  NOT NULL, -- DECIMAL | Money must be exact
  brand     VARCHAR(60)    NOT NULL,
  stock     INT            NOT NULL,
  PRIMARY KEY (id),
  KEY id_category_price (category, price)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- orders - one row per purchase
-- -----------------------------------------------------------------------------
CREATE TABLE orders (
  id          BIGINT    NOT NULL AUTO_INCREMENT,
  user_id     INT       NOT NULL,
  product_id  INT       NOT NULL,
  qty         INT       NOT NULL,
  created_at  DATETIME  NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_orders_product FOREIGN KEY (product_id) REFERENCES products (id)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- carts - one row per shopper with an open cart
-- -----------------------------------------------------------------------------
CREATE TABLE carts (
  user_id     INT       NOT NULL,
  updated_at  DATETIME  NOT NULL,
  PRIMARY KEY (user_id),
  KEY id_updated (updated_at)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- cart_items - what is inside each cart
-- -----------------------------------------------------------------------------
CREATE TABLE cart_items (
  user_id     INT  NOT NULL,
  product_id  INT  NOT NULL,
  qty         INT  NOT NULL,
  PRIMARY KEY (user_id, product_id)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- price_history - one price per product per point in time
-- -----------------------------------------------------------------------------
CREATE TABLE price_history (
  product_id  INT            NOT NULL,
  `time`      DATETIME       NOT NULL,
  price       DECIMAL(10,2)  NOT NULL,
  PRIMARY KEY (product_id, `time`) -- the doc's primary key
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- cart_seed / cart_seed_items - seed data for the cart simulation
-- -----------------------------------------------------------------------------
CREATE TABLE cart_seed (
  user_id  INT  NOT NULL,
  age_min  INT  NOT NULL,
  PRIMARY KEY (user_id)
) ENGINE=InnoDB;

CREATE TABLE cart_seed_items (
  user_id     INT  NOT NULL,
  product_id  INT  NOT NULL,
  qty         INT  NOT NULL,
  PRIMARY KEY (user_id, product_id)
) ENGINE=InnoDB;
