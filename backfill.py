import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import psycopg2

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SHEET_ID = "1efA12VMqJZrXCB7WkySNfKxCVtwe90hnKRSxZyphxRI"

creds = service_account.Credentials.from_service_account_file(
    os.getenv("GOOGLE_SHEETS_KEY_FILE"), scopes=SCOPES
)
service = build("sheets", "v4", credentials=creds)

def fetch_rows(tab_range):
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=tab_range
    ).execute()
    return result.get("values", [])

sales_rows = fetch_rows("Sales Malejor!A2:C")
purchases_rows = fetch_rows("Purchases Malejor!A2:C")

conn = psycopg2.connect(
    dbname="sauce_plata",
    user="postgres",
    password=os.getenv("DB_PASSWORD"),
    host="localhost",
    port="5432",
)
cur = conn.cursor()

cur.execute("TRUNCATE staging_sales;")
cur.executemany(
    "INSERT INTO staging_sales (date, total_sales_cedis, total_sales_usd) VALUES (%s, %s, %s);",
    sales_rows,
)

cur.execute("TRUNCATE staging_purchases;")
cur.executemany(
    "INSERT INTO staging_purchases (date, item, price) VALUES (%s, %s, %s);",
    purchases_rows,
)

conn.commit()
print(f"Inserted {len(sales_rows)} sales rows, {len(purchases_rows)} purchases rows.")

cur.close()
conn.close()