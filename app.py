import streamlit as st
import pandas as pd
import os
import time

import dashboard
import ingredients
import meal_builder
import business_costs

# --- AUTH ---
st.set_page_config(page_title="Clean Eats Costings", layout="wide")

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

SESSION_TIMEOUT = 3600  # 1 hour
password = st.secrets["general"]["access_password"]

if 'login_time' in st.session_state:
    if time.time() - st.session_state.login_time > SESSION_TIMEOUT:
        st.session_state.authenticated = False
        st.warning("🔒 Session expired. Please re-enter your password.")
        st.rerun()

if not st.session_state.authenticated:
    with st.form("login_form"):
        st.subheader("🔐 Enter Access Password")
        input_pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Enter")
        if submitted:
            if input_pw == password:
                st.session_state.authenticated = True
                st.session_state.login_time = time.time()
                st.rerun()
            else:
                st.error("Incorrect password")
    st.stop()

# --- FILE PATHS ---
DATA_FILE = "stored_total_summary.csv"
INGREDIENTS_FILE = "ingredients.csv"
BUSINESS_COSTS_FILE = "business_costs.csv"

# --- INITIALIZE DATA ---
def initialize_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        return pd.DataFrame(columns=["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"])

def initialize_ingredients():
    if os.path.exists(INGREDIENTS_FILE):
        return pd.read_csv(INGREDIENTS_FILE)
    else:
        return pd.DataFrame(columns=["Ingredient", "Unit Type", "Purchase Size", "Cost", "Cost per Unit"])

def initialize_business_costs():
    if os.path.exists(BUSINESS_COSTS_FILE):
        return pd.read_csv(BUSINESS_COSTS_FILE)
    else:
        return pd.DataFrame(columns=["Name", "Type", "Amount", "Unit"])

# --- SAVE DATA ---
def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def save_ingredients(df):
    df.to_csv(INGREDIENTS_FILE, index=False)

def save_business_costs(df):
    df.to_csv(BUSINESS_COSTS_FILE, index=False)

# --- LOAD DATA ---
if "total_df" not in st.session_state:
    st.session_state.total_df = initialize_data()

if "ingredients_df" not in st.session_state:
    st.session_state.ingredients_df = initialize_ingredients()

if "business_costs_df" not in st.session_state:
    st.session_state.business_costs_df = initialize_business_costs()

# --- PAGE UI ---
st.title("📊 Clean Eats Meal Costings")
st.markdown("Use the tabs to view and manage ingredients, meals, business costs, and cost breakdowns.")

tab1, tab2, tab3, tab4 = st.tabs(["💰 Costing Dashboard", "📋 Ingredients", "🍽️ Meals", "⚙️ Business Costs"])

with tab1:
    dashboard.render(st)

with tab2:
    ingredients.render(st)

with tab3:
    meal_builder.render(st)

with tab4:
    business_costs.render(st)
