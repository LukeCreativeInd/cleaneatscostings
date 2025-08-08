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
# Load access password once and cache in session_state to persist across reruns
if "access_password" not in st.session_state:
    st.session_state["access_password"] = st.secrets.get("access_password")
password = st.session_state["access_password"]
if password is None:
    st.error("⚠️ Access password not configured in secrets['access_password'].")
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
# Move title and description above tabs to ensure consistent placement
st.title("📊 Clean Eats Meal Costings")
st.markdown("Use the tabs to view and manage ingredients, meals, business costs, and cost breakdowns.")

# -----------------------------
# Faux tabs (radio) with sticky selection
# -----------------------------
# CSS to style the horizontal radio like tabs
st.markdown(
    """
    <style>
    /* Container for our faux tabs */
    #tabbar [role="radiogroup"] {
        display: flex;
        gap: 0;
        border-bottom: 1px solid rgba(49,51,63,0.2);
        margin-bottom: 0.75rem;
        padding-bottom: 0;
    }
    /* Each option wrapper */
    #tabbar [role="radiogroup"] > label {
        padding: 0;
        margin: 0 6px 0 0;
        background: transparent;
        border: 0;
    }
    /* Hide the default radio dot/icon */
    #tabbar [role="radiogroup"] svg { display: none; }

    /* The clickable "tab" surface */
    #tabbar [role="radiogroup"] > label > div[role="radio"] {
        border: 1px solid rgba(49,51,63,0.15);
        border-bottom: none;
        border-radius: 8px 8px 0 0;
        background: #f7f8fa;
        padding: 8px 14px;
        cursor: pointer;
        transition: background 0.15s ease, border-color 0.15s ease;
        white-space: nowrap;
    }
    /* Selected tab */
    #tabbar [role="radiogroup"] > label > div[role="radio"][aria-checked="true"] {
        background: var(--background-color);
        border-color: rgba(49,51,63,0.3);
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Persisted nav labels (match your old tab titles)
NAV_LABELS = ["💰 Costing Dashboard", "📋 Ingredients", "🍽️ Meals", "⚙️ Business Costs"]
st.session_state.setdefault("active_tab", "💰 Costing Dashboard")

st.markdown('<div id="tabbar">', unsafe_allow_html=True)
choice = st.radio(
    "Navigation",
    NAV_LABELS,
    horizontal=True,
    label_visibility="hidden",
    index=NAV_LABELS.index(st.session_state["active_tab"]),
    key="tab_selector",
)
st.markdown('</div>', unsafe_allow_html=True)

# Persist selection so reruns keep you on the same tab
st.session_state["active_tab"] = choice

# --- SESSION DATA LOAD ---
DATA_FILE = "data/stored_total_summary.csv"
INGREDIENTS_FILE = "data/ingredients.csv"
BUSINESS_COSTS_FILE = "data/business_costs.csv"

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

# --- RENDER PAGES (one at a time) ---
if choice == "💰 Costing Dashboard":
    dashboard.render()
elif choice == "📋 Ingredients":
    ingredients.render()
elif choice == "🍽️ Meals":
    meal_builder.render()
else:  # "⚙️ Business Costs"
    business_costs.render()
