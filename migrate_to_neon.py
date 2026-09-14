import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

local_conn = psycopg2.connect(
    dbname="sauce_plata",
    user="postgres",
    password=os.getenv("DB_PASSWORD"),
    host="localhost",
    port="5432",
)
neon_conn = psycopg2.connect(os.getenv("NEON_DATABASE_URL"))

local_cur = local_conn.cursor()
neon_cur = neon_conn.cursor()

neon_cur.execute("""
    DROP TABLE IF EXISTS purchases;
    CREATE TABLE purchases (
        purchase_date DATE,
        item TEXT,
        price NUMERIC
    );

    DROP TABLE IF EXISTS sales;
    CREATE TABLE sales (
        sale_date DATE,
        total_sales_cedis NUMERIC,
        total_sales_usd NUMERIC
    );

    DROP TABLE IF EXISTS item_classification;
    CREATE TABLE item_classification (
        raw_item TEXT PRIMARY KEY,
        standard_name TEXT NOT NULL,
        is_food BOOLEAN NOT NULL
    );

    DROP TABLE IF EXISTS operational_costs;
    CREATE TABLE operational_costs (
        cost_date DATE,
        price NUMERIC
    );
""")

local_cur.execute("SELECT purchase_date, item, price FROM purchases;")
rows = local_cur.fetchall()
neon_cur.executemany("INSERT INTO purchases (purchase_date, item, price) VALUES (%s, %s, %s);", rows)
print(f"Migrated {len(rows)} purchases rows.")

local_cur.execute("SELECT sale_date, total_sales_cedis, total_sales_usd FROM sales;")
rows = local_cur.fetchall()
neon_cur.executemany("INSERT INTO sales (sale_date, total_sales_cedis, total_sales_usd) VALUES (%s, %s, %s);", rows)
print(f"Migrated {len(rows)} sales rows.")

local_cur.execute("SELECT raw_item, standard_name, is_food FROM item_classification;")
rows = local_cur.fetchall()
neon_cur.executemany("INSERT INTO item_classification (raw_item, standard_name, is_food) VALUES (%s, %s, %s);", rows)
print(f"Migrated {len(rows)} item_classification rows.")

local_cur.execute("SELECT cost_date, price FROM operational_costs;")
rows = local_cur.fetchall()
neon_cur.executemany("INSERT INTO operational_costs (cost_date, price) VALUES (%s, %s);", rows)
print(f"Migrated {len(rows)} operational_costs rows.")

neon_cur.execute("GRANT SELECT ON purchases, sales, operational_costs TO qa_readonly;")
print("Re-granted qa_readonly SELECT access (dropping/recreating tables wipes prior grants).")

neon_conn.commit()
local_cur.close()
neon_cur.close()
local_conn.close()
neon_conn.close()