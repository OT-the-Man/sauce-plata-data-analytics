import os
import re
import requests
from google import genai

SCHEMA = """
Table: purchases
- purchase_date DATE
- item TEXT (standardized ingredient name)
- price NUMERIC (amount paid, in Ghanaian Cedis/GHS)
One row per ingredient purchased.

Table: sales
- sale_date DATE
- total_sales_cedis NUMERIC (total sales that day, in GHS)
- total_sales_usd NUMERIC (total sales that day, in USD)
One row per day (daily aggregate, no item-level sales data exists).

Table: operational_costs
- cost_date DATE
- price NUMERIC (amount spent, in GHS)
One row per non-food operational expense (rent, utilities, payroll, packaging, equipment, etc.) — deliberately has no item-level detail, just date and amount, since these were excluded from the food-item cleaning/standardization done for `purchases`.

Profit note: real profit = sales minus BOTH food costs (`purchases`) AND non-food operational costs (`operational_costs`). If a question asks about "profit" or "how much did we make," you MUST include operational_costs in the deduction, not just purchases — using only purchases understates real costs and overstates profit.
"""

FORBIDDEN = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|CREATE)\b", re.IGNORECASE)

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_secret(name):
    import streamlit as st
    return os.getenv(name) or st.secrets.get(name)

def get_exchange_rate():
    """Returns (ghs_per_usd, source_note)."""
    try:
        response = requests.get("https://open.er-api.com/v6/latest/GHS", timeout=5)
        response.raise_for_status()
        data = response.json()
        rate = 1 / data["rates"]["USD"]
        return rate, "live rate, fetched just now"
    except Exception:
        fallback_rate = float(get_secret("GHS_PER_USD_FALLBACK") or 11)
        fallback_date = get_secret("GHS_PER_USD_FALLBACK_DATE") or "unknown date"
        return fallback_rate, f"manual fallback rate, last set {fallback_date} — live lookup failed"

def format_history(history):
    if not history:
        return "(no previous questions this session)"
    lines = []
    for turn in history[-5:]:
        lines.append(f'Q: "{turn["question"]}"\nA: {turn["answer"]}')
    return "\n\n".join(lines)

def question_to_sql(client, question, history=None):
    prompt = f"""You are a Postgres SQL expert. Given this schema:

{SCHEMA}

Recent conversation in this session (for resolving follow-up questions only):
{format_history(history)}

Current question:
"{question}"

If the current question is a follow-up that leaves something unstated (e.g. it changes the time period but not the product, or changes the product but not the time period, or says things like "what about X"), infer the missing part from the conversation above. Only carry over parts of context the new question doesn't explicitly override.

Write ONE read-only SELECT query (Postgres syntax) that answers the current question, using that inferred context where needed.

Important: item names in the `item` column are specific standardized names (e.g. "Chicken Drumsticks", "Carrots", "Green Pepper"), not general categories. Never match them with exact equality (`=`). Always use case-insensitive partial matching instead, e.g. `item ILIKE '%chicken%'`, so a general term like "chicken" correctly matches every specific chicken item.

Return ONLY the raw SQL query. No markdown fences, no explanation, no semicolon-separated multiple statements."""
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    sql = response.text.strip().strip("`").strip()
    if sql.lower().startswith("sql"):
        sql = sql[3:].strip()
    return sql

def validate_sql(sql):
    stripped = sql.strip().rstrip(";")
    if not stripped.lower().startswith("select"):
        raise ValueError("Generated query is not a SELECT statement — refusing to run it.")
    if FORBIDDEN.search(stripped):
        raise ValueError("Generated query contains a disallowed keyword — refusing to run it.")
    if ";" in stripped:
        raise ValueError("Generated query contains multiple statements — refusing to run it.")
    return stripped

def result_to_answer(client, question, sql, columns, rows):
    ghs_per_usd, rate_note = get_exchange_rate()
    prompt = f"""Question: "{question}"
SQL used: {sql}
Columns: {columns}
Result rows: {rows}

Currency notes:
- Any amount from the `purchases` table (column `price`) is in Ghanaian Cedis (GHS) ONLY.
- Any amount from the `operational_costs` table (column `price`) is also in GHS ONLY.
- Any amount from the `sales` table's `total_sales_cedis` column is GHS; `total_sales_usd` is already a real recorded USD figure — use it directly, do not recompute it.
- Current exchange rate: 1 USD = {ghs_per_usd:.2f} GHS ({rate_note}).

Formatting rule — every GHS amount in your answer MUST be immediately followed by its USD equivalent in this exact format, no exceptions: "GHS <amount> (USD <amount>)" — the word GHS, one space, the number, then USD equivalent in parentheses computed with the exchange rate above.
Example: if a result is 3841.0 GHS, write it as: GHS 3841.0 (USD 349.18)
Do not write a bare GHS amount without its USD equivalent in parentheses right after it. A `total_sales_usd` value is already real USD — still show it the same way, e.g.: GHS 860.00 (USD 78.18).

Answer the question in one or two plain sentences, using the real numbers from the result. Do not mention SQL or databases."""
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return response.text.strip()