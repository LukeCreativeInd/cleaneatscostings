import streamlit as st
import pandas as pd

def render():
    st.header("🍽️ Meal Builder")

    ingredients_df = st.session_state.ingredients_df.copy()
    business_df = st.session_state.business_costs_df.copy()

    meal_name = st.text_input("Meal Name")

    if "meal_rows" not in st.session_state:
        st.session_state.meal_rows = []

    st.subheader("🧪 Assign Ingredients")

    cols = st.columns([3, 2, 1])
    with cols[0]:
        selected_ingredient = st.selectbox("Ingredient", ingredients_df["Ingredient"].unique(), key="ingredient_select")
    with cols[1]:
        quantity = st.number_input("Qty per Meal", min_value=0.0, step=1.0, key="ingredient_qty")
    with cols[2]:
        if st.button("➕ Add"):
            st.session_state.meal_rows.append({
                "Ingredient": selected_ingredient,
                "Quantity per Meal": quantity
            })

    meal_df = pd.DataFrame(st.session_state.meal_rows)
    st.dataframe(meal_df, use_container_width=True)

    def calculate_ingredient_cost():
        total = 0
        for _, row in meal_df.iterrows():
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

    sell_price = st.number_input("Sell Price", min_value=0.0, value=0.0, step=0.5)

    if st.button("💾 Save Meal"):
        with st.spinner("Saving meal..."):
            ingredients_summary = ", ".join([
                f"{row['Ingredient']} ({row['Quantity per Meal']})"
                for _, row in meal_df.iterrows()
                if pd.notna(row['Ingredient']) and pd.notna(row['Quantity per Meal'])
            ])

            new_entry = pd.DataFrame([{
                "Meal": meal_name,
                "Ingredients": ingredient_cost,
                "Other Costs": business_cost,
                "Total Cost": total_cost,
                "Sell Price": sell_price
            }])

            st.session_state.total_df = pd.concat([st.session_state.total_df, new_entry], ignore_index=True)
            from app import save_data
            save_data(st.session_state.total_df)
            st.success("✅ Meal saved!")
            st.session_state.meal_rows = []
            st.rerun()
