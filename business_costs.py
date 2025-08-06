import streamlit as st
import pandas as pd
import os
from datetime import date

# ----------------------
# Config
# ----------------------
DATA_PATH = "data/business_costs.csv"

COST_TYPE_OPTIONS = [
    "Rent",
    "Utilities",
    "PPE",
    "Cleaning & Sanitation",
    "Packaging",
    "Tape & Labels",
    "Labour",
    "Wastage",
    "Delivery",
    "Marketing",
    "Other"
]

UNIT_OPTIONS = [
    "per item",
    "per meal",
    "per delivery",
    "per day",
    "per week",
    "per month",
    "per hour",
    "flat",
    "one-off"
]

# ----------------------
# Data handling
# ----------------------
from meal_builder import commit_file_to_github  # for GitHub commits

def load_business_costs():
    """
    Load business costs from CSV if present; parse date columns if available.
    """
    if os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH)
        # Standardize column names
        df.columns = [col.strip() for col in df.columns]
        # Parse date columns
        for date_col in ["Effective From", "End Date"]:
            if date_col in df.columns:
                df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
        return df
    return pd.DataFrame(
        columns=["Name", "Cost Type", "Amount", "Unit", "Effective From", "End Date"]
    )

def save_business_costs(df: pd.DataFrame):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    df.to_csv(DATA_PATH, index=False)
    # Commit to GitHub
    try:
        commit_file_to_github(DATA_PATH, "data/business_costs.csv", "Update business costs")
    except Exception as e:
        st.warning(f"⚠️ GitHub commit failed: {e}")(df: pd.DataFrame):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    df.to_csv(DATA_PATH, index=False)

# ----------------------
# Main render
# ----------------------
def render():
    st.header("⚙️ Business Costs")
    st.info("Manage and track your recurring business expenses here.")

    df = load_business_costs()

    # Add new cost form
    st.subheader("Add New Business Cost")
    with st.form("add_cost_form"):  # clear_on_submit omitted to control rerun manually
        c1, c2 = st.columns(2)
        name = c1.text_input("Cost Name")
        cost_type = c2.selectbox("Cost Type", COST_TYPE_OPTIONS)

        c3, c4 = st.columns(2)
        amount = c3.number_input("Amount", min_value=0.0, step=0.01)
        unit = c4.selectbox("Unit", UNIT_OPTIONS)

        c5, c6 = st.columns(2)
        eff_from = c5.date_input("Effective From", value=date.today())
        end_date = c6.date_input("End Date (optional)", value=None)

        submitted = st.form_submit_button("➕ Add Cost")
        if submitted:
            if not name.strip():
                st.warning("Please enter a Cost Name.")
            else:
                new_row = {
                    "Name": name.strip(),
                    "Cost Type": cost_type,
                    "Amount": amount,
                    "Unit": unit,
                    "Effective From": eff_from,
                    "End Date": end_date or pd.NaT,
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_business_costs(df)
                st.success(f"Added cost '{name.strip()}' successfully.")
                st.rerun()

    # Display and edit existing costs
    st.subheader("Existing Business Costs")
    if df.empty:
        st.write("No business costs recorded yet.")
    else:
        edited = st.data_editor(df, num_rows="dynamic")
        if st.button("💾 Save Changes", key="save_business_costs"):
            save_business_costs(edited)
            st.success("Business costs updated successfully.")
