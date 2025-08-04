import streamlit as st
import pandas as pd
import os

MEAL_DATA_PATH = "data/meals.csv"
INGREDIENTS_PATH = "data/ingredients.csv"


def load_meals():
    if os.path.exists(MEAL_DATA_PATH):
        return pd.read_csv(MEAL_DATA_PATH)
    return pd.DataFrame(columns=["Meal", "Ingredient", "Quantity", "Cost per Unit", "Total Cost"])


def load_ingredients():
    if os.path.exists(INGREDIENTS_PATH):
        df = pd.read_csv(INGREDIENTS_PATH)
        # Normalize column names (strip + title case)
        df.columns = df.columns.str.strip()
        rename_map = {col: col.strip().title() for col in df.columns}
        df = df.rename(columns=rename_map)

        # Ensure Ingredient column exists and is cleaned
        if "Ingredient" not in df.columns:
            df["Ingredient"] = ""
        df["Ingredient"] = df["Ingredient"].astype(str).str.strip()

        # Ensure cost per unit exists / derive if possible
        if "Cost Per Unit" not in df.columns:
            if "Cost" in df.columns and "Purchase Size" in df.columns:
                def compute_cpu(row):
                    try:
                        purchase_size = float(row["Purchase Size"])
                        cost = float(row["Cost"])
                        return round(cost / purchase_size, 4) if purchase_size != 0 else 0
                    except Exception:
                        return 0

                df["Cost Per Unit"] = df.apply(compute_cpu, axis=1)
            else:
                df["Cost Per Unit"] = 0
        return df
    return pd.DataFrame(
        columns=["Ingredient", "Unit Type", "Purchase Size", "Cost", "Cost Per Unit"]
    )


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

    # Normalize ingredient names for selectbox and keep in memory for callbacks
    ingredients_df["Ingredient"] = ingredients_df["Ingredient"].astype(str).str.strip().str.title()
    ingredient_options = sorted(ingredients_df["Ingredient"].dropna().unique())

    # Session state defaults
    st.session_state.setdefault("meal_name", "")
    st.session_state.setdefault(
        "meal_ingredients",
        pd.DataFrame(
            columns=["Ingredient", "Quantity", "Cost per Unit", "Total Cost"]
        ),
    )
    st.session_state.setdefault("new_meal_quantity", 0.0)
    if "new_meal_ingredient" not in st.session_state:
        # Pre-fill with first ingredient if available, else empty string
        st.session_state.new_meal_ingredient = ingredient_options[0] if ingredient_options else ""

    # Callbacks

    def add_ingredient_callback():
        meal_name = st.session_state.meal_name.strip()
        ingredient = st.session_state.new_meal_ingredient
        quantity = st.session_state.new_meal_quantity

        if not meal_name:
            st.warning("Enter a meal name before adding ingredients.")
            return
        if not ingredient or quantity <= 0:
            st.warning("Ingredient and quantity must be provided and quantity must be greater than zero.")
            return

        # Lookup cost per unit (case-insensitive match)
        match = ingredients_df[
            ingredients_df["Ingredient"].str.lower() == str(ingredient).strip().lower()
        ]
        if match.empty or "Cost Per Unit" not in match.columns:
            st.error(f"Cost lookup failed for ingredient '{ingredient}'.")
            return

        try:
            cpu = float(match.iloc[0]["Cost Per Unit"])
        except Exception:
            st.error(f"Invalid cost data for '{ingredient}'.")
            return

        total_cost = round(cpu * quantity, 4)
        new_row = {
            "Ingredient": ingredient,
            "Quantity": quantity,
            "Cost per Unit": cpu,
            "Total Cost": total_cost,
        }

        # Append
        updated = pd.concat(
            [st.session_state.meal_ingredients, pd.DataFrame([new_row])],
            ignore_index=True,
        )
        st.session_state.meal_ingredients = updated

        # Reset input quantity (but keep ingredient selection)
        st.session_state.new_meal_quantity = 0.0

    def save_meal_callback():
        meal_name = st.session_state.meal_name.strip()
        ingredients = st.session_state.meal_ingredients

        if not meal_name or ingredients.empty:
            st.warning("Meal name and at least one ingredient are required.")
            return

        try:
            current = meals_df.copy()
            new_meal = ingredients.copy()
            new_meal.insert(0, "Meal", meal_name)
            combined = pd.concat([current, new_meal], ignore_index=True)

            os.makedirs("data", exist_ok=True)
            combined.to_csv(MEAL_DATA_PATH, index=False)

            st.success("✅ Meal saved!")
            # Reset builder state
            st.session_state.meal_name = ""
            st.session_state.meal_ingredients = pd.DataFrame(
                columns=["Ingredient", "Quantity", "Cost per Unit", "Total Cost"]
            )
            st.session_state.new_meal_quantity = 0.0
        except Exception as e:
            st.error(f"Failed to save meal: {e}")

    # UI layout
    st.text_input("Meal Name", key="meal_name")

    ingredient_col, quantity_col, add_col = st.columns([3, 2, 1])
    with ingredient_col:
        st.selectbox(
            "Ingredient",
            options=ingredient_options,
            key="new_meal_ingredient",
            help="Select an ingredient to add to the meal.",
        )
    with quantity_col:
        st.number_input(
            "Qty",
            min_value=0.0,
            step=0.1,
            key="new_meal_quantity",
        )
    with add_col:
        st.button("➕ Add Ingredient", on_click=add_ingredient_callback)

    if not st.session_state.meal_ingredients.empty:
        st.subheader(f"🧾 Ingredients for '{st.session_state.meal_name}'")
        st.dataframe(st.session_state.meal_ingredients, use_container_width=True)

    st.button("💾 Save Meal", on_click=save_meal_callback)
