import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import psycopg2

load_dotenv()

# --- Test 1: Google Sheets API auth ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = service_account.Credentials.from_service_account_file(
    os.getenv("GOOGLE_SHEETS_KEY_FILE"), scopes=SCOPES
)
service = build("sheets", "v4", credentials=creds)
sheet_id = "1efA12VMqJZrXCB7WkySNfKxCVtwe90hnKRSxZyphxRI"
result = service.spreadsheets().values().get(
    spreadsheetId=sheet_id, range="Purchases Malejor!A1:C3"
).execute()
print("Sheets API OK, sample rows:", result.get("values"))

# --- Test 2: Postgres connection ---
conn = psycopg2.connect(
    dbname="sauce_plata",
    user="postgres",
    password=os.getenv("DB_PASSWORD"),
    host="localhost",
    port="5432",
)
print("Postgres OK, connected:", conn.status == 1)
conn.close()