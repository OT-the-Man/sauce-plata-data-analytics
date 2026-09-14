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

Currency aliasing rule (required, so the result can be formatted correctly without asking you again): alias every monetary result column with a name ending in `_ghs` (amount is in Ghanaian Cedis) or `_usd` (amount is already in US Dollars, e.g. `sales.total_sales_usd`). Example: `SELECT SUM(price) AS total_ghs FROM purchases ...`. Non-monetary columns (dates, item names, counts) do not need this suffix.

Return ONLY the raw SQL query. No markdown fences, no explanation, no semicolon-separated multiple statements."""
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    sql = response.text.strip().strip("`").strip()
    if sql.lower().startswith("sql"):
        sql = sql[3:].strip()
    return sql

def validate_sql(sql):
    stripped = sql.strip().rstrip(";")
    lower = stripped.lower()
    if not (lower.startswith("select") or lower.startswith("with")):
        raise ValueError("Generated query is not a SELECT statement — refusing to run it.")
    if FORBIDDEN.search(stripped):
        raise ValueError("Generated query contains a disallowed keyword — refusing to run it.")
    if ";" in stripped:
        raise ValueError("Generated query contains multiple statements — refusing to run it.")
    return stripped

def humanize(column_name):
    name = re.sub(r"_(ghs|usd)$", "", column_name, flags=re.IGNORECASE)
    return name.replace("_", " ").strip().capitalize() or "Result"

def format_value(column_name, value):
    lower = column_name.lower()
    if value is None:
        return "none"
    if lower.endswith("_ghs"):
        ghs_per_usd, _ = get_exchange_rate()
        return f"GHS {float(value):.2f} (USD {float(value) / ghs_per_usd:.2f})"
    if lower.endswith("_usd"):
        return f"USD {float(value):.2f}"
    return str(value)

def format_answer(columns, rows):
    """Builds the final answer in plain Python — no second Gemini call needed,
    which also guarantees the currency formatting instead of hoping the model follows it."""
    if not rows:
        return "No matching data found."

    if len(rows) == 1 and len(columns) == 1:
        return f"{humanize(columns[0])}: {format_value(columns[0], rows[0][0])}."

    if len(rows) == 1:
        parts = [f"{humanize(col)}: {format_value(col, val)}" for col, val in zip(columns, rows[0])]
        return ", ".join(parts) + "."

    lines = []
    for row in rows[:20]:
        parts = [f"{humanize(col)}: {format_value(col, val)}" for col, val in zip(columns, row)]
        lines.append("- " + ", ".join(parts))
    suffix = f"\n(...and {len(rows) - 20} more rows)" if len(rows) > 20 else ""
    return "\n".join(lines) + suffix