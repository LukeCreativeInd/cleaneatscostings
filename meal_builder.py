import streamlit as st
import pandas as pd
import os
import uuid

MEAL_DATA_PATH = "data/meals.csv"
INGREDIENTS_PATH = "data/ingredients.csv"

def load_meals():
    if os.path.exists(MEAL_DATA_PATH):
        return pd.read_csv(MEAL_DATA_PATH)
    return pd.DataFrame(columns=["Meal", "Ingredient", "Quantity", "Cost per Unit", "Total Cost"])

def load_ingredients():
    if os.path.exists(INGREDIENTS_PATH):
        df = pd.read_csv(INGREDIENTS_PATH)
        df.columns = df.columns.str.strip().str.title()
        if "Cost Per Unit" not in df.columns and "Cost" in df.columns and "Purchase Size" in df.columns:
            df["Cost per Unit"] = df.apply(
                lambda row: round(float(row["Cost"]) / float(row["Purchase Size"]), 4)
                if row["Purchase Size"] != 0 else 0,
                axis=1
            )
        return df
    return pd.DataFrame(columns=["Ingredient", "Unit Type", "Purchase Size", "Cost", "Cost per Unit"])

def render():
    st.header("🍽️ Meal Builder")
    st.info(
        """Use this tab to build meals by assigning ingredients with specific quantities.

- Begin by naming your meal.
- Add one or more ingredients and their required quantity.
- The system pulls ingredient costs and calculates total cost for the meal.
"""
    )

    meals_df = load_meals()
    ingredients_df = load_ingredients()

    if "meal_name" not in st.session_state:
        st.session_state.meal_name = ""

    st.text_input("Meal Name", key="meal_name")

    if "meal_ingredients" not in st.session_state:
        st.session_state.meal_ingredients = pd.DataFrame(columns=["Ingredient", "Quantity", "Cost per Unit", "Total Cost"])

    ingredient_col, quantity_col, add_col = st.columns([3, 2, 1])
    with ingredient_col:
        ingredient = st.selectbox("Ingredient", ingredients_df["Ingredient"].dropna().unique(), key="new_meal_ingredient")
    with quantity_col:
        quantity = st.number_input("Qty", min_value=0.0, step=0.1, key="new_meal_quantity")
    with add_col:
        if st.button("➕ Add Ingredient"):
            if st.session_state.meal_name and ingredient and quantity:
                match = ingredients_df[ingredients_df["Ingredient"] == ingredient]
                if not match.empty and "Cost per Unit" in match.columns:
                    cpu = match.iloc[0]["Cost per Unit"]
                    total_cost = round(cpu * quantity, 4)
                    new_row = {
                        "Ingredient": ingredient,
                        "Quantity": quantity,
                        "Cost per Unit": cpu,
                        "Total Cost": total_cost
                    }
                    st.session_state.meal_ingredients = pd.concat(
                        [st.session_state.meal_ingredients, pd.DataFrame([new_row])],
                        ignore_index=True
                    )
                    del st.session_state["new_meal_ingredient"]
                    del st.session_state["new_meal_quantity"]
                    st.rerun()
                else:
                    st.error("Selected ingredient is missing cost data.")
            else:
                st.warning("Enter a meal name and ingredient details before adding.")

    if not st.session_state.meal_ingredients.empty:
        st.subheader(f"🧾 Ingredients for '{st.session_state.meal_name}'")
        st.dataframe(st.session_state.meal_ingredients, use_container_width=True)

    if st.button("💾 Save Meal"):
        if st.session_state.meal_name and not st.session_state.meal_ingredients.empty:
            current = meals_df.copy()
            new_meal = st.session_state.meal_ingredients.copy()
            new_meal.insert(0, "Meal", st.session_state.meal_name)
            meals_df = pd.concat([current, new_meal], ignore_index=True)
            os.makedirs("data", exist_ok=True)
            meals_df.to_csv(MEAL_DATA_PATH, index=False)
            st.success("✅ Meal saved!")
            st.session_state.meal_name = ""
            st.session_state.meal_ingredients = pd.DataFrame(columns=["Ingredient", "Quantity", "Cost per Unit", "Total Cost"])
            st.rerun()
        else:
            st.warning("Meal name and at least one ingredient are required.")
