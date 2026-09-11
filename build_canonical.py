import os
import re
from datetime import date as date_type
from dotenv import load_dotenv
import psycopg2

load_dotenv()

conn = psycopg2.connect(
    dbname="sauce_plata",
    user="postgres",
    password=os.getenv("DB_PASSWORD"),
    host="localhost",
    port="5432",
)
cur = conn.cursor()

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

def parse_date(raw):
    raw = raw.strip()
    # format: "10th August" (no year) -> assume 2026
    m = re.match(r"^(\d+)(st|nd|rd|th)\s+([A-Za-z]+)$", raw)
    if m:
        day, month_name = int(m.group(1)), m.group(3).lower()
        return date_type(2026, MONTHS[month_name], day)
    # format: "January 1, 2026"
    m = re.match(r"^([A-Za-z]+)\s+(\d+),\s*(\d{4})$", raw)
    if m:
        month_name, day, year = m.group(1).lower(), int(m.group(2)), int(m.group(3))
        return date_type(year, MONTHS[month_name], day)
    raise ValueError(f"Unrecognized date format: {raw!r}")

# --- Purchases: forward-fill blank dates using original sheet row order, then parse ---
cur.execute("SELECT id, date, item, price FROM staging_purchases ORDER BY id;")
rows = cur.fetchall()

last_date_str = None
filled = []
for id_, raw_date, item, price in rows:
    raw_date = raw_date.strip()
    if raw_date:
        last_date_str = raw_date
    filled.append((parse_date(last_date_str), item, price))

# --- Load item classification for food filter ---
cur.execute("SELECT raw_item, standard_name, is_food FROM item_classification;")
classification = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

final_purchases = []
final_operational_costs = []
for parsed_date, item, price in filled:
    standard_name, is_food = classification.get(item, (None, False))
    if is_food:
        final_purchases.append((parsed_date, standard_name, float(price)))
    else:
        final_operational_costs.append((parsed_date, float(price)))

cur.execute("DROP TABLE IF EXISTS purchases;")
cur.execute("""
    CREATE TABLE purchases (
        purchase_date DATE,
        item TEXT,
        price NUMERIC
    );
""")
cur.executemany(
    "INSERT INTO purchases (purchase_date, item, price) VALUES (%s, %s, %s);",
    final_purchases,
)
print(f"Inserted {len(final_purchases)} purchase rows.")

cur.execute("DROP TABLE IF EXISTS operational_costs;")
cur.execute("""
    CREATE TABLE operational_costs (
        cost_date DATE,
        price NUMERIC
    );
""")
cur.executemany(
    "INSERT INTO operational_costs (cost_date, price) VALUES (%s, %s);",
    final_operational_costs,
)
print(f"Inserted {len(final_operational_costs)} operational cost rows.")

# --- Sales: no blank/ordinal dates, just currency strings to strip ---
cur.execute("SELECT date, total_sales_cedis, total_sales_usd FROM staging_sales;")
sales_rows = cur.fetchall()

final_sales = []
for raw_date, cedis, usd in sales_rows:
    parsed_date = parse_date(raw_date)
    cedis_num = float(cedis.replace("GHS", "").replace(",", "").strip())
    usd_num = float(usd.replace("$", "").replace(",", "").strip())
    final_sales.append((parsed_date, cedis_num, usd_num))

cur.execute("DROP TABLE IF EXISTS sales;")
cur.execute("""
    CREATE TABLE sales (
        sale_date DATE,
        total_sales_cedis NUMERIC,
        total_sales_usd NUMERIC
    );
""")
cur.executemany(
    "INSERT INTO sales (sale_date, total_sales_cedis, total_sales_usd) VALUES (%s, %s, %s);",
    final_sales,
)
print(f"Inserted {len(final_sales)} sales rows.")

conn.commit()
cur.close()
conn.close()