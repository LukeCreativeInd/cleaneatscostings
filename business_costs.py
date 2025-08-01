import streamlit as st
import pandas as pd

BUSINESS_COST_TYPES = [
    "Packaging", "Wages", "Utilities", "Rent", "Transport", "Overheads", "Admin", "Other"
]

COST_UNIT_OPTIONS = [
    "$ / meal", "$ / week", "$ / month", "$", "¢ / meal", "Other"
]

def render():
    st.header("⚙️ Business Costs")
    st.info("Use this tab to manage recurring or per-meal costs like wages, packaging, rent, and other overheads.\n\n**'Amount'** is the numeric cost value.\n**'Unit'** explains what the amount is based on, such as per meal or per week.")

    full_df = st.session_state.business_costs_df.copy()

    st.subheader("📦 Saved Business Costs")
    edited_saved_df = st.data_editor(
        full_df,
        num_rows="dynamic",
        use_container_width=True,
        key="saved_business_costs"
    )

    st.divider()
    st.subheader("➕ New Business Cost Entry")
    if "new_business_entry_df" not in st.session_state:
        st.session_state.new_business_entry_df = pd.DataFrame(columns=["Name", "Type", "Amount", "Unit"])

    new_rows = st.session_state.new_business_entry_df.copy()

    with st.form("add_cost_form"):
        cols = st.columns([3, 2, 2, 2])
        with cols[0]:
            name = st.text_input("Cost Name")
        with cols[1]:
            cost_type = st.selectbox("Type", BUSINESS_COST_TYPES)
        with cols[2]:
            amount = st.number_input("Amount", min_value=0.0, step=1.0)
        with cols[3]:
            unit = st.selectbox("Unit", COST_UNIT_OPTIONS, index=0)

        add = st.form_submit_button("➕ Add Cost")
        if add and name and amount:
            new_rows.loc[len(new_rows)] = {
                "Name": name,
                "Type": cost_type,
                "Amount": amount,
                "Unit": unit
            }
            st.session_state.new_business_entry_df = new_rows

    if not new_rows.empty:
        st.dataframe(new_rows, use_container_width=True)

    if st.button("💾 Save Business Costs"):
        with st.spinner("Saving business costs..."):
            combined = pd.concat([edited_saved_df, new_rows], ignore_index=True)
            st.session_state.business_costs_df = combined

            from app import save_business_costs
            save_business_costs(combined)

            st.success("✅ Business costs saved!")
            st.session_state.new_business_entry_df = pd.DataFrame(columns=["Name", "Type", "Amount", "Unit"])
            st.rerun()
