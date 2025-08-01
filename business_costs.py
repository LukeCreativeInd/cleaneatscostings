import streamlit as st
import pandas as pd

def render():
    st.header("⚙️ Business Costs")
    st.write("Define fixed or variable costs associated with operations")

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

    edited_new_df = st.data_editor(
        st.session_state.new_business_entry_df,
        num_rows="dynamic",
        use_container_width=True,
        key="new_business_costs"
    )

    if st.button("💾 Save Business Costs"):
        with st.spinner("Saving business costs..."):
            new_df = edited_new_df.copy()
            saved_df = edited_saved_df.copy()

            combined = pd.concat([saved_df, new_df], ignore_index=True)
            st.session_state.business_costs_df = combined

            from app import save_business_costs
            save_business_costs(combined)

            st.success("✅ Business costs saved!")
            st.session_state.new_business_entry_df = pd.DataFrame(columns=["Name", "Type", "Amount", "Unit"])

            import streamlit.runtime.scriptrunner.script_run_context as script_context
            from streamlit.runtime.scriptrunner import RerunException
            raise RerunException(script_context.get_script_run_ctx())
