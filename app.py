import streamlit as st
import pandas as pd
import os

# Modular pages
import dashboard
import ingredients
import meal_builder
import business_costs

# --- CONFIG ---
st.set_page_config(page_title="Clean Eats Costings", layout="wide")

# --- SECRETS ---
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

# --- PAGE LAYOUT ---
st.title("📊 Clean Eats Meal Costings")
st.markdown("Use the tabs to view and manage ingredients, meals, business costs, and cost breakdowns.")

# --- PAGE NAVIGATION with dynamic tab order ---
ALL_TABS = [
    "💰 Costing Dashboard",
    "📋 Ingredients",
    "🍽️ Meals",
    "⚙️ Business Costs",
]
# Default to last visited tab or dashboard
active_tab = st.session_state.get("last_active_tab", "💰 Costing Dashboard")
# Order tabs so the active_tab is first
tab_order = [active_tab] + [t for t in ALL_TABS if t != active_tab]
tabs = st.tabs(tab_order)

# --- SESSION DATA LOAD ---
DATA_FILE = "data/stored_total_summary.csv"
INGREDIENTS_FILE = "data/ingredients.csv"
BUSINESS_COSTS_FILE = "data/business_costs.csv"

# Initialize dataframes in session state
if "total_df" not in st.session_state:
    st.session_state.total_df = pd.read_csv(DATA_FILE) if os.path.exists(DATA_FILE) else pd.DataFrame(
        columns=["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"]
    )
if "ingredients_df" not in st.session_state:
    st.session_state.ingredients_df = pd.read_csv(INGREDIENTS_FILE) if os.path.exists(INGREDIENTS_FILE) else pd.DataFrame(
        columns=["Ingredient", "Unit Type", "Purchase Size", "Cost", "Cost per Unit"]
    )
if "business_costs_df" not in st.session_state:
    st.session_state.business_costs_df = pd.read_csv(BUSINESS_COSTS_FILE) if os.path.exists(BUSINESS_COSTS_FILE) else pd.DataFrame(
        columns=["Name", "Type", "Amount", "Unit"]
    )

# --- RENDER PAGES ---
for label, tab in zip(tab_order, tabs):
    with tab:
        # Persist the current tab for next rerun
        st.session_state["last_active_tab"] = label
        # Dispatch to modules
        if label == "💰 Costing Dashboard":
            dashboard.render()
        elif label == "📋 Ingredients":
            ingredients.render()
        elif label == "🍽️ Meals":
            meal_builder.render()
        else:
            business_costs.render()
