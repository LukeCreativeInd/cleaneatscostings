import streamlit as st
import pandas as pd

UNIT_TYPE_OPTIONS = ["KG", "L", "Unit"]

def render():
    st.header("📋 Ingredient Manager")
    st.info("Use this tab to manage ingredients used in meals.\n\n**'Purchase Size'** is how much you buy at once (e.g. 5KG).\n**'Unit Type'** specifies if it's in kilograms, litres, or units.\n**'Cost'** is the total cost for the full purchase size.\n\nThe system calculates cost per unit automatically.")

    full_df = st.session_state.ingredients_df.copy()

    def live_cost_per_unit(row):
        try:
            return round(float(row["Cost"]) / float(row["Purchase Size"]), 4)
        except (ValueError, ZeroDivisionError, TypeError):
            return None

    saved_df = full_df.dropna(subset=["Ingredient"]).copy()
    saved_df["Cost per Unit"] = saved_df.apply(live_cost_per_unit, axis=1)

    st.subheader("🧾 Saved Ingredients")
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

    new_rows = st.session_state.new_entry_df.copy()

    with st.form("add_ingredient_form"):
        cols = st.columns([3, 2, 2, 2])
        with cols[0]:
            name = st.text_input("Ingredient Name", value="", key="ingredient_name")
        with cols[1]:
            unit_type = st.selectbox("Unit Type", UNIT_TYPE_OPTIONS)
        with cols[2]:
            purchase_size = st.number_input("Purchase Size", min_value=0.0, step=0.1)
        with cols[3]:
            cost = st.number_input("Cost", min_value=0.0, step=0.1)

        add = st.form_submit_button("➕ Add Ingredient")
        if add and name and purchase_size:
            new_rows.loc[len(new_rows)] = {
                "Ingredient": name,
                "Unit Type": unit_type,
                "Purchase Size": purchase_size,
                "Cost": cost
            }
            st.session_state.new_entry_df = new_rows
            st.session_state.ingredient_name = ""
            st.rerun()

    if not new_rows.empty:
        new_rows["Cost per Unit"] = new_rows.apply(live_cost_per_unit, axis=1)
        st.dataframe(new_rows, use_container_width=True)

    if st.button("💾 Save Ingredients"):
        with st.spinner("Saving ingredients..."):
            combined = pd.concat([edited_saved_df, new_rows], ignore_index=True)
            combined["Cost per Unit"] = combined.apply(live_cost_per_unit, axis=1)
            st.session_state.ingredients_df = combined

            from app import save_ingredients
            save_ingredients(combined)

            st.success("✅ Ingredients saved!")
            st.session_state.new_entry_df = pd.DataFrame(columns=["Ingredient", "Unit Type", "Purchase Size", "Cost"])
            st.rerun()
