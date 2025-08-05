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
# Use .get to avoid KeyError if unset
password = st.secrets.get("access_password")
if password is None:
    st.error("⚠️ Access password not configured in secrets['access_password'.]")
    st.stop()

# --- SESSION LOGIN STATE ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    with st.form("login_form"):
        st.subheader("🔐 Enter Access Password")
        input_pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if input_pw == password:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Incorrect password")
    st.stop()

# --- FILE PATHS & INITIALIZERS ---
DATA_FILE = "data/stored_total_summary.csv"
INGREDIENTS_FILE = "data/ingredients.csv"
BUSINESS_COSTS_FILE = "data/business_costs.csv"


def initialize_data():
    return pd.read_csv(DATA_FILE) if os.path.exists(DATA_FILE) else pd.DataFrame(
        columns=["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"]
    )


def initialize_ingredients():
    return pd.read_csv(INGREDIENTS_FILE) if os.path.exists(INGREDIENTS_FILE) else pd.DataFrame(
        columns=["Ingredient", "Unit Type", "Purchase Size", "Cost", "Cost per Unit"]
    )


def initialize_business_costs():
    return pd.read_csv(BUSINESS_COSTS_FILE) if os.path.exists(BUSINESS_COSTS_FILE) else pd.DataFrame(
        columns=["Name", "Type", "Amount", "Unit"]
    )

# --- SESSION DATA LOAD ---
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
