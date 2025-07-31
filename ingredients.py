import streamlit as st
import pandas as pd

def render(st):
    st.header("📋 Ingredient Manager")

    full_df = st.session_state.ingredients_df.copy()

    def live_cost_per_unit(row):
        try:
            return round(float(row["Cost"]) / float(row["Purchase Size"]), 4)
        except (ValueError, ZeroDivisionError, TypeError):
            return None

    saved_df = full_df.dropna(subset=["Ingredient"]).copy()
    saved_df["Cost per Unit"] = saved_df.apply(live_cost_per_unit, axis=1)

    st.subheader("🗃️ Saved Ingredients")
    edited_saved_df = st.data_editor(
        saved_df,
        num_rows="dynamic",
        use_container_width=True,
        key="saved_ingredients"
    )

    st.divider()
    st.subheader("➕ New Ingredient Entry")
    if "new_entry_df" not in st.session_state:
        st.session_state.new_entry_df = pd.DataFrame(columns=["Ingredient", "Unit Type", "Purchase Size", "Cost"])

    edited_new_df = st.data_editor(
        st.session_state.new_entry_df,
        num_rows="dynamic",
        use_container_width=True,
        key="new_ingredients"
    )

    if st.button("💾 Save Ingredients"):
        with st.spinner("Saving ingredients..."):
            new_df = edited_new_df.copy()
            saved_df = edited_saved_df.copy()
            combined = pd.concat([saved_df, new_df], ignore_index=True)
            combined["Cost per Unit"] = combined.apply(live_cost_per_unit, axis=1)
            st.session_state.ingredients_df = combined
            from app import save_ingredients
            save_ingredients(combined)
            st.success("✅ Ingredients saved!")
            st.session_state.new_entry_df = pd.DataFrame(columns=["Ingredient", "Unit Type", "Purchase Size", "Cost"])
            st.experimental_rerun()
