import streamlit as st
import pandas as pd
import os
import time

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

# --- UI LAYOUT ---
st.title("📊 Clean Eats Meal Costings")
st.markdown("Use the side panel to view and manage ingredients, meals, and cost breakdowns.")

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["💰 Costing Dashboard", "📋 Ingredients", "🍽️ Meals"])

with tab1:
    st.header("💰 Costing Dashboard")
    df = st.session_state.total_df.copy()

    if not df.empty:
        df["Profit Margin"] = df["Sell Price"] - df["Total Cost"]
        df["Margin %"] = (df["Profit Margin"] / df["Sell Price"]) * 100
        st.dataframe(df.style.format({
            "Ingredients": "$ {:.2f}",
            "Other Costs": "$ {:.2f}",
            "Total Cost": "$ {:.2f}",
            "Sell Price": "$ {:.2f}",
            "Profit Margin": "$ {:.2f}",
            "Margin %": "{:.1f}%"
        }), use_container_width=True)
    else:
        st.warning("📂 No costing data yet. You can upload one-time data below to initialise.")

    uploaded_file = st.file_uploader("Initialise from costing spreadsheet (one-time import)", type=["xlsx"])
    if uploaded_file:
        raw_df = pd.read_excel(uploaded_file, sheet_name="TOTAL")
        raw_df = raw_df.rename(columns={
            "DESCRIPTION MEAL": "Meal",
            "RAW MATERIAL": "Ingredients",
            "ROADMAP": "Other Costs",
            "TOTAL": "Total Cost",
            "SELL COST": "Sell Price"
        })
        clean_df = raw_df[["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"]]
        st.session_state.total_df = clean_df
        save_data(clean_df)
        st.success("✅ Data imported and saved!")
        st.rerun()

with tab2:
    st.header("📋 Ingredient Manager")

    full_df = st.session_state.ingredients_df.copy()

    def live_cost_per_unit(row):
        try:
            return round(float(row["Cost"]) / float(row["Purchase Size"]), 4)
        except (ValueError, ZeroDivisionError, TypeError):
            return None

    saved_df = full_df.dropna(subset=["Ingredient"]).copy()
    saved_df["Cost per Unit"] = saved_df.apply(live_cost_per_unit, axis=1)

    st.subheader("🗃️ Saved Ingredients")
    edited_saved_df = st.data_editor(saved_df, num_rows="dynamic", use_container_width=True, key="saved_ingredients")

    st.divider()
    st.subheader("➕ New Ingredient Entry")
    if "new_entry_df" not in st.session_state:
        st.session_state.new_entry_df = pd.DataFrame(columns=["Ingredient", "Unit Type", "Purchase Size", "Cost"])

    edited_new_df = st.data_editor(st.session_state.new_entry_df, num_rows="dynamic", use_container_width=True, key="new_ingredients")

    if st.button("💾 Save Ingredients"):
        with st.spinner("Saving ingredients..."):
            new_df = edited_new_df.copy()
            saved_df = edited_saved_df.copy()
            combined = pd.concat([saved_df, new_df], ignore_index=True)
            combined["Cost per Unit"] = combined.apply(live_cost_per_unit, axis=1)
            st.session_state.ingredients_df = combined
            save_ingredients(combined)
            st.session_state.new_entry_df = pd.DataFrame(columns=["Ingredient", "Unit Type", "Purchase Size", "Cost"])
            st.success("✅ Ingredients saved and new entries cleared!")
            st.rerun()

with tab3:
    st.header("🍽️ Meal Builder")
    st.info("This section will allow editing meals, assigning ingredients, and dynamically calculating cost. Coming soon!")

with st.sidebar.expander("⚙️ Business Costs", expanded=False):
    st.write("Define fixed or variable costs associated with operations")

    saved_costs_df = st.session_state.business_costs_df.copy()

    st.subheader("📦 Saved Business Costs")
    edited_costs_df = st.data_editor(saved_costs_df, num_rows="dynamic", use_container_width=True, key="saved_business_costs")

    if st.button("💾 Save Business Costs"):
        with st.spinner("Saving business costs..."):
            st.session_state.business_costs_df = edited_costs_df
            save_business_costs(edited_costs_df)
            st.success("✅ Business costs saved!")
