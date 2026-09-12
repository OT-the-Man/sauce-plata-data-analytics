import os
import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st
from dotenv import load_dotenv

import qa

load_dotenv()

st.set_page_config(page_title="Sauce Plata Dashboard", layout="wide")

def get_connection():
    db_url = os.getenv("NEON_DATABASE_URL") or st.secrets["NEON_DATABASE_URL"]
    return psycopg2.connect(db_url)

def get_qa_connection():
    db_url = os.getenv("QA_DATABASE_URL") or st.secrets["QA_DATABASE_URL"]
    return psycopg2.connect(db_url)

conn = get_connection()
sales = pd.read_sql("SELECT sale_date, total_sales_cedis, total_sales_usd FROM sales ORDER BY sale_date;", conn)
purchases = pd.read_sql("SELECT purchase_date, item, price FROM purchases ORDER BY purchase_date;", conn)
operational_costs = pd.read_sql("SELECT cost_date, price FROM operational_costs ORDER BY cost_date;", conn)
conn.close()

st.title("Sauce Plata — Purchasing & Sales Dashboard")

st.header("Sales over time")
fig_sales = px.line(sales, x="sale_date", y="total_sales_cedis", title="Daily Total Sales (GHS)")
st.plotly_chart(fig_sales, use_container_width=True)

st.header("Food purchases over time")
daily_purchases = purchases.groupby("purchase_date")["price"].sum().reset_index()
fig_purchases = px.line(daily_purchases, x="purchase_date", y="price", title="Daily Ingredient Spend (GHS)")
st.plotly_chart(fig_purchases, use_container_width=True)

st.header("Top ingredients by total spend")
top_items = purchases.groupby("item")["price"].sum().sort_values(ascending=False).head(15).reset_index()
fig_top = px.bar(top_items, x="price", y="item", orientation="h", title="Top 15 Ingredients by Spend (GHS)")
fig_top.update_layout(yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig_top, use_container_width=True)

st.header("Sales vs Costs by month")
sales["month"] = pd.to_datetime(sales["sale_date"]).dt.to_period("M").astype(str)
purchases["month"] = pd.to_datetime(purchases["purchase_date"]).dt.to_period("M").astype(str)
operational_costs["month"] = pd.to_datetime(operational_costs["cost_date"]).dt.to_period("M").astype(str)
monthly_sales = sales.groupby("month")["total_sales_cedis"].sum().reset_index(name="Sales")
monthly_purchases = purchases.groupby("month")["price"].sum().reset_index(name="Food Purchases")
monthly_operational = operational_costs.groupby("month")["price"].sum().reset_index(name="Operational Costs")
monthly = pd.merge(monthly_sales, monthly_purchases, on="month", how="outer")
monthly = pd.merge(monthly, monthly_operational, on="month", how="outer").fillna(0).sort_values("month")
monthly_long = monthly.melt(id_vars="month", value_vars=["Sales", "Food Purchases", "Operational Costs"], var_name="Type", value_name="Amount")
fig_monthly = px.bar(monthly_long, x="month", y="Amount", color="Type", barmode="group", title="Monthly Sales vs Food Purchases vs Operational Costs (GHS)")
st.plotly_chart(fig_monthly, use_container_width=True)

st.header("Ask a question")

if "qa_history" not in st.session_state:
    st.session_state.qa_history = []

for turn in st.session_state.qa_history:
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        st.write(turn["answer"])
        with st.expander("Show SQL used"):
            st.code(turn["sql"], language="sql")

question = st.chat_input("Ask about the purchasing/sales data, e.g. \"how much did we spend on chicken last month?\"")
if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                client = qa.get_client()
                sql = qa.question_to_sql(client, question, st.session_state.qa_history)
                sql = qa.validate_sql(sql)

                qa_conn = get_qa_connection()
                qa_cur = qa_conn.cursor()
                qa_cur.execute(sql)
                columns = [desc[0] for desc in qa_cur.description]
                rows = qa_cur.fetchall()
                qa_cur.close()
                qa_conn.close()

                answer = qa.format_answer(columns, rows)
                st.write(answer)
                with st.expander("Show SQL used"):
                    st.code(sql, language="sql")
                st.session_state.qa_history.append({"question": question, "sql": sql, "answer": answer})
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                print(f"Q&A error: {type(e).__name__}: {e}")
                if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                    st.warning("The free daily limit for the Q&A feature has been reached. It resets once a day — please try again later.")
                else:
                    st.warning("Q&A is busy right now, try again in a minute.")