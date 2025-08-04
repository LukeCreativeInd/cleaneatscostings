import streamlit as st
import pandas as pd
import os
import requests
import base64
from datetime import datetime
from io import StringIO

MEAL_DATA_PATH = "data/meals.csv"
INGREDIENTS_PATH = "data/ingredients.csv"


def load_meals():
    if os.path.exists(MEAL_DATA_PATH):
        df = pd.read_csv(MEAL_DATA_PATH)
        df.columns = df.columns.str.strip().str.title()
        return df
    return pd.DataFrame(columns=["Meal", "Ingredient", "Quantity", "Cost Per Unit", "Total Cost"])


def load_ingredients():
    # Prefer shared state if provided by the Ingredients tab
    if "ingredients_df" in st.session_state and isinstance(st.session_state.ingredients_df, pd.DataFrame):
        df = st.session_state.ingredients_df.copy()
        df.columns = df.columns.str.strip().str.title()
    elif os.path.exists(INGREDIENTS_PATH):
        df = pd.read_csv(INGREDIENTS_PATH)
        df.columns = df.columns.str.strip().str.title()
    else:
        return pd.DataFrame(
            columns=["Ingredient", "Unit Type", "Purchase Size", "Cost", "Cost Per Unit"]
        )

    # Ensure cost per unit exists or compute it
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

    df["Ingredient"] = df["Ingredient"].astype(str).str.strip().str.title()
    return df


def save_meals_to_github(df: pd.DataFrame):
    """Commit meals.csv to GitHub (mirrors the pattern in utils.py)."""
    os.makedirs("data", exist_ok=True)
    df.to_csv(MEAL_DATA_PATH, index=False)

    try:
        token = st.secrets["github_token"]
        repo = st.secrets["github_repo"]
        branch = st.secrets.get("github_branch", "main")
        path = "data/meals.csv"

        api_url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"
        }

        # Get existing file to retrieve sha if it exists
        get_resp = requests.get(api_url, headers=headers, params={"ref": branch})
        if get_resp.status_code == 200:
            sha = get_resp.json().get("sha")
        else:
            sha = None

        content = base64.b64encode(df.to_csv(index=False).encode()).decode()
        data = {
            "message": f"Update meals at {datetime.utcnow().isoformat()}Z",
            "content": content,
            "branch": branch
        }
        if sha:
            data["sha"] = sha

        put_resp = requests.put(api_url, headers=headers, json=data)
        if put_resp.status_code not in [200, 201]:
            st.error(f"GitHub commit failed: {put_resp.status_code} {put_resp.text}")
        else:
            st.success("✅ meals.csv committed to GitHub")
    except KeyError:
        st.warning("GitHub secrets missing; saved locally but did not push to repo.")
    except Exception as e:
        st.error(f"Failed to commit meals.csv to GitHub: {e}")


def render():
    st.header("🍽️ Meal Builder")
    st.info(
        """Use this tab to build meals by assigning ingredients with specific quantities.

- Begin by naming your meal.
- Add one or more ingredients and their required quantity.
- The system pulls ingredient costs and calculates total cost for the meal.
"""
    )

    # Load data
    meals_df = load_meals()
    ingredients_df = load_ingredients()
    ingredient_options = sorted(ingredients_df["Ingredient"].dropna().unique())

    # Session state defaults
    st.session_state.setdefault("meal_name", "")
    st.session_state.setdefault(
        "meal_ingredients",
        pd.DataFrame(
            columns=["Ingredient", "Quantity", "Cost Per Unit", "Total Cost"]
        ),
    )
    st.session_state.setdefault("new_meal_quantity", 0.0)
    if "new_meal_ingredient" not in st.session_state:
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
            "Cost Per Unit": cpu,
            "Total Cost": total_cost,
        }

        updated = pd.concat(
            [st.session_state.meal_ingredients, pd.DataFrame([new_row])],
            ignore_index=True,
        )
        st.session_state.meal_ingredients = updated
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

            # Auto-commit to GitHub (if secrets are provided)
            save_meals_to_github(combined)

            # Reset builder state
            st.session_state.meal_name = ""
            st.session_state.meal_ingredients = pd.DataFrame(
                columns=["Ingredient", "Quantity", "Cost Per Unit", "Total Cost"]
            )
            st.session_state.new_meal_quantity = 0.0

            # Refresh the page so the saved meals section updates
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Failed to save meal: {e}")

    # UI inputs
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
        st.subheader(f"🧾 Ingredients for '{st.session_state.meal_name}' (unsaved)")
        st.dataframe(st.session_state.meal_ingredients, use_container_width=True)

    st.button("💾 Save Meal", on_click=save_meal_callback)

    # Display saved meals & download
    with st.expander("📦 Saved Meals", expanded=True):
        meals_df = load_meals()  # reload to reflect persisted state
        if not meals_df.empty:
            meal_names = sorted(meals_df["Meal"].dropna().unique())
            selected_meal = st.selectbox("Filter to meal:", options=["(all)"] + meal_names)
            if selected_meal != "(all)":
                filtered = meals_df[meals_df["Meal"] == selected_meal]
            else:
                filtered = meals_df.copy()

            if selected_meal != "(all)":
                st.markdown(f"**Summary for '{selected_meal}':**")
                total_cost = filtered["Total Cost"].sum()
                st.write(f"- Ingredients: {len(filtered)}")
                st.write(f"- Total cost: {total_cost:.4f}")

            st.dataframe(filtered, use_container_width=True)

            csv_buffer = StringIO()
            meals_df.to_csv(csv_buffer, index=False)
            st.download_button(
                label="Download full meals.csv",
                data=csv_buffer.getvalue(),
                file_name="meals.csv",
                mime="text/csv",
            )
        else:
            st.write("No meals have been saved yet.")
