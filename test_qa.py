import os
import traceback
from dotenv import load_dotenv
load_dotenv()
import psycopg2
import qa

try:
    client = qa.get_client()
    sql = qa.question_to_sql(client, "what is the profit in June 2026", [])
    print("SQL generated:", sql)
    sql = qa.validate_sql(sql)
    print("SQL validated OK")

    conn = psycopg2.connect(os.getenv("QA_DATABASE_URL"))
    cur = conn.cursor()
    cur.execute(sql)
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    print("DB result:", columns, rows)

    answer = qa.result_to_answer(client, "what is the profit in June 2026", sql, columns, rows)
    print("FINAL ANSWER:", answer)
except Exception:
    print("FULL ERROR:")
    traceback.print_exc()
