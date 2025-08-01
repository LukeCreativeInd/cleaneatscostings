import streamlit as st
import pandas as pd
import os
import time

# Modular tabs
import dashboard
import ingredients
import meal_builder
import business_costs

# --- CONFIG ---
st.set_page_config(page_title="Clean Eats Costings", layout="wide")

# --- SECRETS ---
password = st.secrets["general"]["access_password"]
SESSION_TIMEOUT = 3600  # 1 hour

# --- FILE PATHS ---
DATA_FILE = "stored_total_summary.csv"
INGREDIENTS_FILE = "ingredients.csv"
BUSINESS_COSTS_FILE = "business_costs.csv"

# --- SESSION SETUP ---
def initialize_data():
    return pd.read_csv(DATA_FILE) if os.path.exists(DATA_FILE) else pd.DataFrame(columns=["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"])

def initialize_ingredients():
    return pd.read_csv(INGREDIENTS_FILE) if os.path.exists(INGREDIENTS_FILE) else pd.DataFrame(columns=["Ingredient", "Unit Type", "Purchase Size", "Cost", "Cost per Unit"])

def initialize_business_costs():
    return pd.read_csv(BUSINESS_COSTS_FILE) if os.path.exists(BUSINESS_COSTS_FILE) else pd.DataFrame(columns=["Name", "Type", "Amount", "Unit"])

def save_data(df): df.to_csv(DATA_FILE, index=False)
def save_ingredients(df): df.to_csv(INGREDIENTS_FILE, index=False)
def save_business_costs(df): df.to_csv(BUSINESS_COSTS_FILE, index=False)

# --- LOGIN CHECK ---
query_params = st.query_params
logged_in = query_params.get("access", [""])[0] == "ok"

if not logged_in:
    with st.form("login_form"):
        st.subheader("🔐 Enter Access Password")
        input_pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if input_pw == password:
                st.experimental_set_query_params(access="ok")
                st.rerun()
            else:
                st.error("Incorrect password")
    st.stop()

# --- LOAD DATA TO SESSION ---
if "total_df" not in st.session_state:
    st.session_state.total_df = initialize_data()

if "ingredients_df" not in st.session_state:
    st.session_state.ingredients_df = initialize_ingredients()

if "business_costs_df" not in st.session_state:
    st.session_state.business_costs_df = initialize_business_costs()

# --- PAGE LAYOUT ---
st.title("📊 Clean Eats Meal Costings")
st.markdown("Use the tabs to view and manage ingredients, meals, business costs, and cost breakdowns.")

tab1, tab2, tab3, tab4 = st.tabs([
    "💰 Costing Dashboard",
    "📋 Ingredients",
    "🍽️ Meals",
    "⚙️ Business Costs"
])

with tab1:
    dashboard.render()

with tab2:
    ingredients.render()

with tab3:
    meal_builder.render()

with tab4:
    business_costs.render()
