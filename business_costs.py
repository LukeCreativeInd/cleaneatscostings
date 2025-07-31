import streamlit as st
import pandas as pd

def render(st):
    st.header("⚙️ Business Costs")
    st.write("Define fixed or variable costs associated with operations")

    saved_costs_df = st.session_state.business_costs_df.copy()

    st.subheader("📦 Saved Business Costs")
    edited_costs_df = st.data_editor(saved_costs_df, num_rows="dynamic", use_container_width=True, key="saved_business_costs")

    if st.button("💾 Save Business Costs"):
        with st.spinner("Saving business costs..."):
            st.session_state.business_costs_df = edited_costs_df
            from app import save_business_costs
            save_business_costs(edited_costs_df)
            st.success("✅ Business costs saved!")
