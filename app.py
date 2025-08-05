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

# --- PAGE NAVIGATION ---
# Use a horizontal radio to emulate tabs and preserve selection across reruns
pages = [
    "💰 Costing Dashboard",
    "📋 Ingredients",
    "🍽️ Meals",
    "⚙️ Business Costs",
]
if "selected_page" not in st.session_state:
    st.session_state.selected_page = pages[0]

# Inject CSS to style the radio like tabs
st.markdown(
    '''
    <style>
    /* Make radiogroup horizontal */
    div[role="radiogroup"] {
        display: flex;
        padding: 0;
        margin: 0;
    }
    /* Each option container flexes equally and centers text */
    div[role="radiogroup"] > div {
        flex: 1;
        text-align: center;
        padding: 0;
        margin: 0;
    }
    /* Hide the original radio inputs */
    div[role="radiogroup"] input[type="radio"] {
        display: none !important;
    }
    /* Style labels as tabs */
    div[role="radiogroup"] label {
        display: block;
        padding: 0.75rem 1rem;
        cursor: pointer;
        border-bottom: 2px solid transparent;
        margin: 0;
    }
    /* Highlight the selected tab */
    div[role="radiogroup"] input[type="radio"]:checked + label {
        font-weight: bold;
        border-color: #FFF; /* White bottom border to stand out on dark background */
    }
    </style>
    ''',
    unsafe_allow_html=True,
)

# Render navigation
current = st.radio("", pages,
                   index=pages.index(st.session_state.selected_page),
                   key="selected_page",
                   label_visibility="collapsed")

# --- SESSION DATA LOAD ---
DATA_FILE = "data/stored_total_summary.csv"
INGREDIENTS_FILE = "data/ingredients.csv"
BUSINESS_COSTS_FILE = "data/business_costs.csv"

# Initialize if not in session
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

# --- PAGE LAYOUT ---
st.title("📊 Clean Eats Meal Costings")
st.markdown("Use the tabs to view and manage ingredients, meals, business costs, and cost breakdowns.")

# Dispatch to the correct page
if current == "💰 Costing Dashboard":
    dashboard.render()
elif current == "📋 Ingredients":
    ingredients.render()
elif current == "🍽️ Meals":
    meal_builder.render()
elif current == "⚙️ Business Costs":
    business_costs.render()
