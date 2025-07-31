import streamlit as st
import pandas as pd
import os

# --- AUTH ---
st.set_page_config(page_title="Clean Eats Costings", layout="wide")

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

password = st.secrets["general"]["access_password"]

if not st.session_state.authenticated:
    with st.form("login_form"):
        st.subheader("🔐 Enter Access Password")
        input_pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Enter")
        if submitted:
            if input_pw == password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password")
    st.stop()

# --- FILE PATHS ---
DATA_FILE = "stored_total_summary.csv"
INGREDIENTS_FILE = "ingredients.csv"

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

# --- SAVE DATA ---
def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def save_ingredients(df):
    df.to_csv(INGREDIENTS_FILE, index=False)

# --- LOAD DATA ---
if "total_df" not in st.session_state:
    st.session_state.total_df = initialize_data()

if "ingredients_df" not in st.session_state:
    st.session_state.ingredients_df = initialize_ingredients()

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

    ing_df = st.session_state.ingredients_df.copy()
    edited_df = st.data_editor(ing_df, num_rows="dynamic", use_container_width=True, key="ingredient_editor")

    if st.button("💾 Save Ingredients"):
        if not edited_df.empty:
            edited_df["Cost per Unit"] = edited_df.apply(lambda row: round(row["Cost"] / row["Purchase Size"], 4) if row["Purchase Size"] else 0, axis=1)
        st.session_state.ingredients_df = edited_df
        save_ingredients(edited_df)
        st.success("✅ Ingredients saved!")

with tab3:
    st.header("🍽️ Meal Builder")
    st.info("This section will allow editing meals, assigning ingredients, and dynamically calculating cost. Coming soon!")
