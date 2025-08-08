import streamlit as st
import pandas as pd
import os

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
    "per meal",     # flat cost added to each meal
    "per carton",   # cost divided by 24 meals
    "per month"     # cost divided by monthly production
]

# ----------------------
# Data handling
# ----------------------
def load_business_costs():
    """
    Load business costs from CSV if present.
    Columns: Name, Cost Type, Amount, Unit
    """
    if os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH)
        df.columns = [col.strip() for col in df.columns]
        # Ensure expected columns
        for c in ["Name", "Cost Type", "Amount", "Unit"]:
            if c not in df.columns:
                df[c] = "" if c in ["Name", "Cost Type", "Unit"] else 0.0
        return df[["Name", "Cost Type", "Amount", "Unit"]]
    return pd.DataFrame(columns=["Name", "Cost Type", "Amount", "Unit"])


def save_business_costs(df: pd.DataFrame):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    df.to_csv(DATA_PATH, index=False)
    # Commit to GitHub if available
    try:
        from meal_builder import commit_file_to_github
        commit_file_to_github(DATA_PATH, "data/business_costs.csv", "Update business costs")
    except Exception as e:
        st.warning(f"⚠️ GitHub commit failed: {e}")

# Draft buffer save
def _save_pending_costs():
    base = load_business_costs()
    pending = st.session_state["pending_costs"]
    out = pd.concat([base, pending], ignore_index=True)
    save_business_costs(out)
    st.success(f"✅ Saved {len(pending)} cost(s).")
    # clear draft buffer (Streamlit will rerun automatically)
    st.session_state["pending_costs"] = pd.DataFrame(columns=["Name", "Cost Type", "Amount", "Unit"])

# ----------------------
# Main render
# ----------------------
def render():
    st.header("⚙️ Business Costs")
    st.info("Manage and track your recurring business expenses here.")

    # Load saved costs
    df = load_business_costs()

    # Init pending buffer (draft list)
    st.session_state.setdefault(
        "pending_costs",
        pd.DataFrame(columns=["Name", "Cost Type", "Amount", "Unit"])
    )

    # Add new cost form (adds to draft)
    st.subheader("Add New Business Cost")
    with st.form("add_cost_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Cost Name")
        cost_type = c2.selectbox("Cost Type", COST_TYPE_OPTIONS)

        c3, c4 = st.columns(2)
        amount = c3.number_input("Amount", min_value=0.0, step=0.01)
        unit = c4.selectbox("Unit", UNIT_OPTIONS)

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
                }
                st.session_state["pending_costs"] = pd.concat(
                    [st.session_state["pending_costs"], pd.DataFrame([new_row])],
                    ignore_index=True
                )
                st.success(f"Added cost '{name.strip()}' to draft list.")

    # Pending draft table + save button
    if not st.session_state["pending_costs"].empty:
        st.subheader("📝 Pending Costs (draft)")
        st.dataframe(st.session_state["pending_costs"], use_container_width=True)
        st.button("💾 Save Pending Costs", on_click=_save_pending_costs)

    # Display and edit existing costs
    st.subheader("Existing Business Costs")
    if df.empty:
        st.write("No business costs recorded yet.")
    else:
        edited = st.data_editor(df, num_rows="dynamic")
        if st.button("💾 Save Changes", key="save_business_costs"):
            save_business_costs(edited)
            st.success("Business costs updated successfully.")
