import streamlit as st
import pandas as pd
import os
import requests
import base64
from datetime import datetime
from io import StringIO

MEAL_DATA_PATH = "data/meals.csv"
INGREDIENTS_PATH = "data/ingredients.csv"

# --- Unit conversion utils ---
def display_to_base(qty, display_unit, base_unit_type):
    t = base_unit_type.upper()
    u = display_unit.lower()
    if t == "KG":
        return qty / 1000.0 if u in ["g", "gram", "grams"] else qty
    if t == "L":
        return qty / 1000.0 if u == "ml" else qty
    return qty


def base_to_display(qty, base_unit_type):
    t = base_unit_type.upper()
    if t == "KG":
        return (qty * 1000.0, "g") if qty < 1 else (qty, "kg")
    if t == "L":
        return (qty * 1000.0, "ml") if qty < 1 else (qty, "L")
    return (qty, "unit")


def get_display_unit_options(base_unit_type):
    t = base_unit_type.upper()
    if t == "KG":
        return ["kg", "g"]
    if t == "L":
        return ["L", "ml"]
    return ["unit"]

# --- Data loaders ---
def load_meals():
    if os.path.exists(MEAL_DATA_PATH):
        df = pd.read_csv(MEAL_DATA_PATH)
        df.columns = df.columns.str.strip()
        return df
    return pd.DataFrame(columns=["Meal", "Ingredient", "Quantity", "Cost per Unit", "Total Cost", "Input Unit"])


def load_ingredients():
    if os.path.exists(INGREDIENTS_PATH):
        df = pd.read_csv(INGREDIENTS_PATH)
        df.columns = df.columns.str.strip().str.title()
        if "Cost Per Unit" not in df.columns:
            df["Cost Per Unit"] = df.apply(
                lambda r: round(float(r.get("Cost", 0)) / float(r.get("Purchase Size", 1)), 6)
                if float(r.get("Purchase Size", 1)) else 0,
                axis=1,
            )
        df["Ingredient"] = df["Ingredient"].astype(str).str.strip().str.title()
        df["Unit Type"] = df.get("Unit Type", "").astype(str).str.strip().str.upper()
        return df
    return pd.DataFrame(columns=["Ingredient", "Unit Type", "Purchase Size", "Cost", "Cost Per Unit"])

# --- GitHub commit helper ---
def commit_file_to_github(local_path, repo_path, message_prefix):
    try:
        token = st.secrets["github_token"]
        repo = st.secrets["github_repo"]
        branch = st.secrets.get("github_branch", "main")
    except KeyError:
        st.warning("GitHub secrets missing; saved locally only.")
        return
    url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    content = base64.b64encode(open(local_path, "rb").read()).decode()
    resp = requests.get(url, headers=headers, params={"ref": branch})
    sha = resp.json().get("sha") if resp.status_code == 200 else None
    payload = {
        "message": f"{message_prefix} {datetime.utcnow().isoformat()}Z",
        "content": content,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    put_resp = requests.put(url, headers=headers, json=payload)
    if put_resp.status_code not in (200, 201):
        st.error(f"GitHub commit failed: {put_resp.status_code} {put_resp.text}")

# --- Meal Builder UI ---
def render():
    st.header("🍽️ Meal Builder")
    st.info(
        """Build meals by adding ingredients with quantities (e.g., 150g from a 10kg bag)."""
    )

    # Load data
    meals_df = load_meals()
    ingredients_df = load_ingredients()
    options = sorted(ingredients_df["Ingredient"].dropna().unique())

    # Session defaults
    st.session_state.setdefault("meal_name", "")
    st.session_state.setdefault(
        "meal_ingredients",
        pd.DataFrame(columns=["Ingredient", "Quantity", "Cost per Unit", "Total Cost", "Input Unit"]),
    )
    st.session_state.setdefault("new_qty", 0.0)
    st.session_state.setdefault("new_unit", None)
    if "new_ing" not in st.session_state:
        st.session_state.new_ing = options[0] if options else ""

    # Save callback
    def save_meal_callback():
        name = st.session_state.meal_name.strip()
        df_ing = st.session_state.meal_ingredients
        if not name or df_ing.empty:
            st.warning("Meal name & at least one ingredient required.")
            return
        combined = pd.concat([meals_df, df_ing.assign(Meal=name)], ignore_index=True)
        os.makedirs("data", exist_ok=True)
        combined.to_csv(MEAL_DATA_PATH, index=False)
        st.success("✅ Meal saved!")
        commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Update meals")
        # Reset state safely before rerun
        st.session_state.meal_name = ""
        st.session_state.meal_ingredients = pd.DataFrame(columns=df_ing.columns)
        st.session_state.new_qty = 0.0
        st.session_state.new_unit = None

    # Add ingredient form
    st.subheader("Create / Add Meal")
    with st.form("add_form"):
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        with col1:
            st.text_input("Meal Name", key="meal_name")
        with col2:
            st.selectbox("Ingredient", options=options, key="new_ing")
        with col3:
            row = ingredients_df[
                ingredients_df["Ingredient"].str.lower()
                == st.session_state.new_ing.lower()
            ].iloc[0]
            base_unit = row.get("Unit Type", "")
            opts = get_display_unit_options(base_unit)
            st.number_input("Qty", key="new_qty", min_value=0.0, step=0.1)
            if st.session_state.new_unit is None:
                st.session_state.new_unit = opts[0] if opts else ""
            st.selectbox("Unit", opts, key="new_unit", label_visibility="collapsed")
        submitted = st.form_submit_button("➕ Add Ingredient to Meal")
        if submitted:
            if not st.session_state.meal_name.strip():
                st.warning("Enter meal name first.")
            else:
                qty = st.session_state.new_qty
                if qty <= 0:
                    st.warning("Quantity must be >0.")
                else:
                    cpu = float(row.get("Cost Per Unit", 0))
                    base_qty = display_to_base(
                        qty, st.session_state.new_unit, base_unit
                    )
                    total_cost = round(base_qty * cpu, 6)
                    entry = {
                        "Ingredient": row["Ingredient"],
                        "Quantity": base_qty,
                        "Cost per Unit": cpu,
                        "Total Cost": total_cost,
                        "Input Unit": st.session_state.new_unit,
                    }
                    st.session_state.meal_ingredients = pd.concat(
                        [st.session_state.meal_ingredients, pd.DataFrame([entry])],
                        ignore_index=True,
                    )
                    st.success(
                        f"Added {qty}{st.session_state.new_unit} of {row['Ingredient']}"
                    )

    # Display ingredients for current meal
    if not st.session_state.meal_ingredients.empty:
        st.subheader(f"🧾 Ingredients for '{st.session_state.meal_name}'")
        temp = st.session_state.meal_ingredients.copy()
        temp["Display"] = temp.apply(
            lambda r: f"{base_to_display(r['Quantity'], ingredients_df[ingredients_df['Ingredient'].str.lower()==r['Ingredient'].lower()].iloc[0]['Unit Type'])[0]:.2f} {r['Input Unit']}",
            axis=1,
        )
        st.dataframe(
            temp[["Ingredient", "Display", "Cost per Unit", "Total Cost"]],
            use_container_width=True,
        )
        st.button("💾 Save Meal", on_click=save_meal_callback)

    # Optional: show saved meals
    st.markdown("---")
    st.subheader("📦 Saved Meals")
    if not meals_df.empty:
        st.table(meals_df)
    else:
        st.write("No meals saved yet.")
