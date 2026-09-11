import os
import csv
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

cur.execute("DROP TABLE IF EXISTS item_classification;")
cur.execute("""
    CREATE TABLE item_classification (
        raw_item TEXT PRIMARY KEY,
        standard_name TEXT NOT NULL,
        is_food BOOLEAN NOT NULL
    );
""")

with open("item_review.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = [
        (r["item"], r["standard_name"].strip(), r["is_food"].strip().upper() == "YES")
        for r in reader
    ]

cur.executemany(
    "INSERT INTO item_classification (raw_item, standard_name, is_food) VALUES (%s, %s, %s);",
    rows,
)

conn.commit()
print(f"Loaded {len(rows)} classification rows.")
cur.close()
conn.close()