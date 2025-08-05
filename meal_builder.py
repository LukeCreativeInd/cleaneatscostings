import streamlit as st
import pandas as pd
import os
import requests
import base64
from datetime import datetime
from io import StringIO

MEAL_DATA_PATH = "data/meals.csv"
INGREDIENTS_PATH = "data/ingredients.csv"

# ----------------------
# Unit conversion utils
# ----------------------
def display_to_base(qty, display_unit, base_unit_type):
    t = (base_unit_type or "").upper()
    u = (display_unit or "").lower()
    if t == "KG":
        return qty / 1000.0 if u in ["g", "gram", "grams"] else qty
    if t == "L":
        return qty / 1000.0 if u == "ml" else qty
    return qty


def base_to_display(qty, base_unit_type):
    t = (base_unit_type or "").upper()
    if t == "KG":
        return (qty * 1000.0, "g") if qty < 1 else (qty, "kg")
    if t == "L":
        return (qty * 1000.0, "ml") if qty < 1 else (qty, "L")
    return (qty, "unit")


def get_display_unit_options(base_unit_type):
    t = (base_unit_type or "").upper()
    if t == "KG": return ["kg", "g"]
    if t == "L": return ["L", "ml"]
    return ["unit"]

# ----------------------
# Data loaders
# ----------------------
def load_meals():
    if os.path.exists(MEAL_DATA_PATH):
        df = pd.read_csv(MEAL_DATA_PATH)
        df.columns = df.columns.str.strip()
        return df
    return pd.DataFrame(columns=["Meal","Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"])


def load_ingredients():
    if os.path.exists(INGREDIENTS_PATH):
        df = pd.read_csv(INGREDIENTS_PATH)
        df.columns = df.columns.str.strip().str.title()
        if "Cost Per Unit" not in df.columns:
            df["Cost Per Unit"] = df.apply(
                lambda r: round(float(r.get("Cost",0)) / float(r.get("Purchase Size",1)),6)
                if float(r.get("Purchase Size",1)) else 0,
                axis=1)
        df["Ingredient"] = df["Ingredient"].astype(str).str.strip().str.title()
        df["Unit Type"] = df.get("Unit Type","").astype(str).str.strip().str.upper()
        return df
    return pd.DataFrame(columns=["Ingredient","Unit Type","Purchase Size","Cost","Cost Per Unit"])

# ----------------------
# GitHub commit helper
# ----------------------
def commit_file_to_github(local_path, repo_path, message_prefix):
    try:
        token = st.secrets["github_token"]
        repo = st.secrets["github_repo"]
        branch = st.secrets.get("github_branch","main")
    except KeyError:
        st.warning("GitHub secrets missing; saved locally only.")
        return
    url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    headers = {"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json"}
    raw = open(local_path, "rb").read()
    content = base64.b64encode(raw).decode()
    resp = requests.get(url, headers=headers, params={"ref":branch})
    sha = resp.json().get("sha") if resp.status_code==200 else None
    payload = {"message":f"{message_prefix} {datetime.utcnow().isoformat()}Z","content":content,"branch":branch}
    if sha: payload["sha"] = sha
    put = requests.put(url, headers=headers, json=payload)
    if put.status_code not in (200,201): st.error(f"GitHub commit failed: {put.status_code} {put.text}")

# ----------------------
# Core rendering
# ----------------------
def render():
    st.header("🍽️ Meal Builder")
    st.info(
        """
Build meals by adding ingredients with quantities.
You can save, view, and edit meals with intuitive controls.
"""
    )

    # Load data
    meals_df = load_meals()
    ingredients_df = load_ingredients()
    ingredient_options = sorted(ingredients_df["Ingredient"].dropna().unique())

    # Session defaults
    st.session_state.setdefault("meal_name", "")
    st.session_state.setdefault(
        "meal_ingredients",
        pd.DataFrame(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"])
    )
    st.session_state.setdefault("new_meal_qty", 0.0)
    st.session_state.setdefault("new_meal_unit", None)
    if "new_meal_ingredient" not in st.session_state:
        st.session_state.new_meal_ingredient = ingredient_options[0] if ingredient_options else ""

    # Reset unit when ingredient changes
    def reset_unit():
        sel = st.session_state.new_meal_ingredient
        info = ingredients_df[ingredients_df["Ingredient"].str.lower() == sel.lower()]
        base = info.iloc[0]["Unit Type"] if not info.empty else ""
        opts = get_display_unit_options(base)
        st.session_state.new_meal_unit = opts[0] if opts else None

    # Add ingredient form
    st.subheader("Create / Add Meal")
    with st.form("new_meal_form", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        with c1:
            st.text_input("Meal Name", key="meal_name")
        with c2:
            st.selectbox(
                "Ingredient",
                ingredient_options,
                key="new_meal_ingredient",
                on_change=reset_unit
            )
        with c3:
            sel = st.session_state.new_meal_ingredient
            info = ingredients_df[ingredients_df["Ingredient"].str.lower() == sel.lower()]
            base_unit = info.iloc[0]["Unit Type"] if not info.empty else ""
            opts = get_display_unit_options(base_unit)
            st.number_input("Qty", min_value=0.0, step=0.1, key="new_meal_qty")
            st.selectbox(
                "Unit",
                opts,
                key="new_meal_unit"
            )
        with c4:
            add = st.form_submit_button("➕ Add Ingredient")
        if add:
            name = st.session_state.meal_name.strip()
            if not name:
                st.warning("Enter meal name first.")
            else:
                qty = st.session_state.new_meal_qty
                unit = st.session_state.new_meal_unit
                if qty <= 0:
                    st.warning("Quantity must be >0")
                else:
                    row = info.iloc[0]
                    cpu = float(row["Cost Per Unit"])
                    bq = display_to_base(qty, unit, row.get("Unit Type", ""))
                    tot = round(bq * cpu, 6)
                    entry = {
                        "Ingredient": row["Ingredient"],
                        "Quantity": bq,
                        "Cost per Unit": cpu,
                        "Total Cost": tot,
                        "Input Unit": unit,
                    }
                    st.session_state.meal_ingredients = pd.concat(
                        [st.session_state.meal_ingredients, pd.DataFrame([entry])],
                        ignore_index=True,
                    )
                    st.success(f"Added {qty}{unit} of {row['Ingredient']}")

    # Save callback
    def save_meal_callback():
        name = st.session_state.meal_name.strip()
        entries = st.session_state.meal_ingredients
        if not name or entries.empty:
            st.warning("Meal name and at least one ingredient required.")
            return
        combined = pd.concat([meals_df, entries.assign(Meal=name)], ignore_index=True)
        os.makedirs("data", exist_ok=True)
        combined.to_csv(MEAL_DATA_PATH, index=False)
        st.success("✅ Meal saved!")
        commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Update meals")
        # Reset
        st.session_state.meal_name = ""
        st.session_state.meal_ingredients = pd.DataFrame(columns=entries.columns)
        st.session_state.new_meal_qty = 0.0
        st.session_state.new_meal_unit = None

    # Display unsaved entries and Save button
    if not st.session_state.meal_ingredients.empty:
        st.subheader(f"🧾 Ingredients for '{st.session_state.meal_name}' (unsaved)")
        temp = st.session_state.meal_ingredients.copy()
        temp["Display"] = temp.apply(
            lambda r: f"{base_to_display(r['Quantity'],
                ingredients_df[ingredients_df['Ingredient']==r['Ingredient']].iloc[0]['Unit Type'])[0]:.2f} {r['Input Unit']}", axis=1
        )
        st.dataframe(
            temp[["Ingredient", "Display", "Cost per Unit", "Total Cost"]],
            use_container_width=True,
        )
        st.button("💾 Save Meal", on_click=save_meal_callback)

    # List and edit saved meals
    st.markdown("---")
    st.subheader("📦 Saved Meals")
    if not meals_df.empty:
        for meal in sorted(meals_df['Meal'].unique()):
            cols = st.columns([6, 1])
            cols[0].markdown(f"**{meal}**")
            if cols[1].button("✏️", key=f"edit_{meal}"):
                st.session_state.editing_meal = meal
    else:
        st.write("No meals saved yet.")

    # Editing modal omitted for brevity
