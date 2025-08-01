import streamlit as st
import pandas as pd


def render():
    st.header("🍽️ Meal Manager")

    ingredients_df = st.session_state.ingredients_df.copy()
    business_df = st.session_state.business_costs_df.copy()
    meal_df = st.session_state.total_df.copy()

    # ------------------------
    # 🔹 SECTION 1: EXISTING MEALS
    # ------------------------
    st.subheader("📝 Existing Meals")

    if not meal_df.empty:
        for i, row in meal_df.iterrows():
            cols = st.columns([4, 2, 2, 2, 2, 1, 1])
            cols[0].markdown(f"**{row['Meal']}**")
            cols[1].markdown(f"${row['Ingredients']:.2f}")
            cols[2].markdown(f"${row['Other Costs']:.2f}")
            cols[3].markdown(f"${row['Total Cost']:.2f}")
            cols[4].markdown(f"${row['Sell Price']:.2f}")
            
            if cols[5].button("✏️", key=f"edit_{i}"):
                st.session_state.editing_meal_index = i
                st.session_state.meal_rows = []  # clear old builder
                st.session_state.editing_meal_name = row['Meal']
                st.session_state.editing_sell_price = row['Sell Price']

            if cols[6].button("🗑️", key=f"delete_{i}"):
                st.session_state.total_df = meal_df.drop(i).reset_index(drop=True)
                from app import save_data
                save_data(st.session_state.total_df)
                st.success(f"🗑️ Deleted '{row['Meal']}'")
                st.rerun()
    else:
        st.info("No meals found. Add a new one below.")

    st.divider()

    # ------------------------
    # 🔸 SECTION 2: MEAL BUILDER
    # ------------------------
    if "meal_rows" not in st.session_state:
        st.session_state.meal_rows = []

    editing = "editing_meal_index" in st.session_state

    st.subheader("➕ New Meal Builder" if not editing else f"✏️ Editing: {st.session_state.editing_meal_name}")

    meal_name = st.text_input("Meal Name", value=st.session_state.get("editing_meal_name", ""))

    cols = st.columns([3, 2, 1])
    with cols[0]:
        selected_ingredient = st.selectbox("Ingredient", ingredients_df["Ingredient"].unique(), key="ingredient_select")
    with cols[1]:
        quantity = st.number_input("Qty per Meal", min_value=0.0, step=1.0, key="ingredient_qty")
    with cols[2]:
        if st.button("➕ Add Ingredient"):
            st.session_state.meal_rows.append({
                "Ingredient": selected_ingredient,
                "Quantity per Meal": quantity
            })

    builder_df = pd.DataFrame(st.session_state.meal_rows)
    st.dataframe(builder_df, use_container_width=True)

    def calculate_ingredient_cost():
        total = 0
        for _, row in builder_df.iterrows():
            match = ingredients_df[ingredients_df["Ingredient"] == row["Ingredient"]]
            if not match.empty:
                cpu = match.iloc[0]["Cost per Unit"]
                qty = row["Quantity per Meal"]
                try:
                    total += float(cpu) * float(qty)
                except:
                    continue
        return round(total, 2)

    ingredient_cost = calculate_ingredient_cost()
    business_cost = round(business_df["Amount"].sum(), 2)
    total_cost = round(ingredient_cost + business_cost, 2)

    st.markdown(f"**Ingredient Cost:** ${ingredient_cost:.2f}")
    st.markdown(f"**Business Cost Applied:** ${business_cost:.2f}")
    st.markdown(f"**Total Cost:** ${total_cost:.2f}")

    sell_price = st.number_input(
        "Sell Price",
        min_value=0.0,
        value=st.session_state.get("editing_sell_price", 0.0),
        step=0.5,
        key="sell_price_input"
    )

    save_button_label = "💾 Save Meal" if not editing else "✅ Update Meal"

    if st.button(save_button_label):
        with st.spinner("Saving meal..."):
            new_entry = pd.DataFrame([{
                "Meal": meal_name,
                "Ingredients": ingredient_cost,
                "Other Costs": business_cost,
                "Total Cost": total_cost,
                "Sell Price": sell_price
            }])

            if editing:
                st.session_state.total_df.iloc[st.session_state.editing_meal_index] = new_entry.iloc[0]
            else:
                st.session_state.total_df = pd.concat([st.session_state.total_df, new_entry], ignore_index=True)

            from app import save_data
            save_data(st.session_state.total_df)

            st.success("✅ Meal saved!")

            # clear all builder + edit states
            st.session_state.meal_rows = []
            st.session_state.editing_meal_name = ""
            st.session_state.editing_sell_price = 0.0
            if "editing_meal_index" in st.session_state:
                del st.session_state.editing_meal_index

            import streamlit.runtime.scriptrunner.script_run_context as script_context
            from streamlit.runtime.scriptrunner import RerunException
            raise RerunException(script_context.get_script_run_ctx())
