import os
import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Sauce Plata Dashboard", layout="wide")

def get_connection():
    db_url = os.getenv("NEON_DATABASE_URL") or st.secrets["NEON_DATABASE_URL"]
    return psycopg2.connect(db_url)

conn = get_connection()
sales = pd.read_sql("SELECT sale_date, total_sales_cedis, total_sales_usd FROM sales ORDER BY sale_date;", conn)
purchases = pd.read_sql("SELECT purchase_date, item, price FROM purchases ORDER BY purchase_date;", conn)
conn.close()

st.title("Sauce Plata — Purchasing & Sales Dashboard")

st.header("Sales over time")
fig_sales = px.line(sales, x="sale_date", y="total_sales_cedis", title="Daily Total Sales (GHS)")
st.plotly_chart(fig_sales, use_container_width=True)

st.header("Purchases over time")
daily_purchases = purchases.groupby("purchase_date")["price"].sum().reset_index()
fig_purchases = px.line(daily_purchases, x="purchase_date", y="price", title="Daily Ingredient Spend (GHS)")
st.plotly_chart(fig_purchases, use_container_width=True)

st.header("Top ingredients by total spend")
top_items = purchases.groupby("item")["price"].sum().sort_values(ascending=False).head(15).reset_index()
fig_top = px.bar(top_items, x="price", y="item", orientation="h", title="Top 15 Ingredients by Spend (GHS)")
fig_top.update_layout(yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig_top, use_container_width=True)

st.header("Sales vs Purchases by month")
sales["month"] = pd.to_datetime(sales["sale_date"]).dt.to_period("M").astype(str)
purchases["month"] = pd.to_datetime(purchases["purchase_date"]).dt.to_period("M").astype(str)
monthly_sales = sales.groupby("month")["total_sales_cedis"].sum().reset_index(name="Sales")
monthly_purchases = purchases.groupby("month")["price"].sum().reset_index(name="Purchases")
monthly = pd.merge(monthly_sales, monthly_purchases, on="month", how="outer").fillna(0).sort_values("month")
monthly_long = monthly.melt(id_vars="month", value_vars=["Sales", "Purchases"], var_name="Type", value_name="Amount")
fig_monthly = px.bar(monthly_long, x="month", y="Amount", color="Type", barmode="group", title="Monthly Sales vs Purchases (GHS)")
st.plotly_chart(fig_monthly, use_container_width=True)