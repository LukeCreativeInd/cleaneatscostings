import streamlit as st
import pandas as pd
import os
import uuid
import base64
import io
import requests
from utils import save_business_costs_to_github

COST_TYPE_OPTIONS = [
    "Packaging", "Labour", "Overhead", "Wastage", "Utilities", "Rent", "Tape/Labels", "Boxes", "Delivery", "Marketing", "Other"
]
UNIT_TYPE_OPTIONS = ["KG", "L", "Unit"]
DATA_PATH = "data/business_costs.csv"

def load_business_costs():
    try:
        token = st.secrets["github_token"]
        repo = st.secrets["github_repo"]
        branch = st.secrets.get("github_branch", "main")
        path = "data/business_costs.csv"

        api_url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(api_url, headers=headers)

        if resp.status_code == 200:
            content = base64.b64decode(resp.json()["content"])
            df = pd.read_csv(io.StringIO(content.decode("utf-8")))
            df.columns = df.columns.str.strip().str.title()
            expected_cols = ["Name", "Type", "Unit", "Amount"]
            df = df[[col for col in df.columns if col in expected_cols]]
            os.makedirs("data", exist_ok=True)
            df.to_csv(DATA_PATH, index=False)
            return df
    except Exception as e:
        st.warning(f"⚠️ Exception loading business costs: {e}")
    return pd.DataFrame(columns=["Name", "Type", "Unit", "Amount"])

def render():
    st.header("📦 Business Costs Manager")
    st.info("Use this tab to manage recurring business costs such as packaging, wages, rent, and more.\n\n**'Unit'** should reflect the measurement type (e.g. per KG, per Litre, per Unit).\n**'Amount'** is the dollar value.")

    business_df = load_business_costs()
    st.session_state.business_costs_df = business_df
    full_df = business_df.copy()

    st.subheader("🧾 Saved Business Costs")
    if full_df.empty:
        st.warning("📄 No saved business costs yet.")
    else:
        edited_df = st.data_editor(
            full_df,
            num_rows="dynamic",
            use_container_width=True,
            key="saved_business_costs"
        )

    st.divider()
    st.subheader("➕ New Business Cost Entry")
    if "business_new_entry_df" not in st.session_state:
        st.session_state.business_new_entry_df = pd.DataFrame(columns=["Name", "Type", "Unit", "Amount"])

    new_rows = st.session_state.business_new_entry_df.copy()

    if "business_cost_form_key" not in st.session_state:
        st.session_state.business_cost_form_key = str(uuid.uuid4())

    form_container = st.empty()
    with form_container.form(key=st.session_state.business_cost_form_key):
        cols = st.columns([3, 2, 2, 2])
        with cols[0]:
            name = st.text_input("Cost Name", key="business_cost_name")
        with cols[1]:
            cost_type = st.selectbox("Cost Type", COST_TYPE_OPTIONS, key="business_cost_type")
        with cols[2]:
            unit = st.selectbox("Unit", UNIT_TYPE_OPTIONS, key="business_cost_unit")
        with cols[3]:
            amount = st.number_input("Amount", min_value=0.0, step=0.1, key="business_cost_amount")

        add = st.form_submit_button("➕ Add Cost")
        if add and name:
            new_rows.loc[len(new_rows)] = {
                "Name": name,
                "Type": cost_type,
                "Unit": unit,
                "Amount": amount
            }
            st.session_state.business_new_entry_df = new_rows
            for key in ["business_cost_name", "business_cost_type", "business_cost_unit", "business_cost_amount"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.business_cost_form_key = str(uuid.uuid4())
            st.rerun()

    if not new_rows.empty:
        st.dataframe(new_rows, use_container_width=True)

    if st.button("💾 Save Business Costs"):
        with st.spinner("Saving business costs..."):
            combined = pd.concat([full_df, new_rows], ignore_index=True)
            st.session_state.business_costs_df = combined
            save_business_costs_to_github(combined)
            st.success("✅ Business costs saved!")
            st.session_state.business_new_entry_df = pd.DataFrame(columns=["Name", "Type", "Unit", "Amount"])
            st.session_state.business_cost_form_key = str(uuid.uuid4())
            st.rerun()
