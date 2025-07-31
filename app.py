import streamlit as st
import pandas as pd

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

# --- LOAD DATA FROM UPLOAD ---
@st.cache_data
def load_total_summary(uploaded_file):
    df = pd.read_excel(uploaded_file, sheet_name="TOTAL")
    st.write("Columns found in uploaded sheet:", df.columns.tolist())  # 🪵 Debug helper
    try:
        df = df.rename(columns={
            "DESCRIPTION": "Meal",
            "MEAL": "Raw Cost",
            "RAW MATERIAL": "Ingredients",
            "ROADMAP": "Other Costs",
            "TOTAL": "Total Cost",
            "SELL COST": "Sell Price"
        })
        return df[["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"]]
    except KeyError as e:
        st.error(f\"❌ Missing expected columns. Check column names in your spreadsheet.\\n\\nDetails: {e}\")
        return pd.DataFrame()

# --- UI LAYOUT ---
st.title("📊 Clean Eats Meal Costings")
st.markdown("Use the side panel to view and manage ingredients, meals, and cost breakdowns.")

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["💰 Costing Dashboard", "📋 Ingredients", "🍽️ Meals"])

with tab1:
    st.header("💰 Costing Dashboard")
    uploaded_file = st.file_uploader("Upload the costing spreadsheet", type=["xlsx"])
    if uploaded_file:
        df = load_total_summary(uploaded_file)
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
        st.warning("📂 Please upload the costing spreadsheet to begin.")

with tab2:
    st.header("📋 Ingredient Manager")
    st.info("This section will allow editing of ingredient name, unit, cost per purchase, and calculate cost per gram/mL/unit. Coming soon!")

with tab3:
    st.header("🍽️ Meal Builder")
    st.info("This section will allow editing meals, assigning ingredients, and dynamically calculating cost. Coming soon!")
