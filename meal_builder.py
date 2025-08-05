import streamlit as st
import pandas as pd
import os
import requests
import base64
from datetime import datetime

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
        df["Unit Type"] = df.get("Unit Type","unit").astype(str).str.strip().str.upper()
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
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    resp = requests.get(url, headers=headers, params={"ref":branch})
    sha = resp.json().get("sha") if resp.status_code==200 else None
    payload = {
        "message": f"{message_prefix} {datetime.utcnow().isoformat()}Z",
        "content": content,
        "branch": branch
    }
    if sha:
        payload["sha"] = sha
    put = requests.put(url, headers=headers, json=payload)
    if put.status_code not in (200,201):
        st.error(f"GitHub commit failed: {put.status_code} {put.text}")

# ----------------------
# Core rendering
# ----------------------
def render():
    st.header("🍽️ Meal Builder")
    st.info("Build meals by adding ingredients with quantities; then save and edit existing meals.")

    meals_df = load_meals()
    ingredients_df = load_ingredients()
    options = sorted(ingredients_df["Ingredient"].unique())

    # Session state defaults
    st.session_state.setdefault("meal_name", "")
    st.session_state.setdefault(
        "meal_ingredients",
        pd.DataFrame(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"])
    )
    st.session_state.setdefault("new_qty", 0.0)
    st.session_state.setdefault("new_unit", None)
    if "new_ing" not in st.session_state:
        st.session_state.new_ing = options[0] if options else ""

    # Reset unit when ingredient changes
    def reset_unit():
        info = ingredients_df[ingredients_df["Ingredient"].str.lower()==st.session_state.new_ing.lower()]
        base = info.iloc[0]["Unit Type"] if not info.empty else "unit"
        opts = get_display_unit_options(base)
        st.session_state.new_unit = opts[0]

    # Add ingredient callback
    def add_callback():
        name = st.session_state.meal_name.strip()
        if not name:
            st.warning("Enter meal name first.")
            return
        qty = st.session_state.new_qty
        if qty <= 0:
            st.warning("Quantity must be >0.")
            return
        ing = st.session_state.new_ing
        unit = st.session_state.new_unit
        row = ingredients_df[ingredients_df["Ingredient"].str.lower()==ing.lower()].iloc[0]
        cpu = float(row["Cost Per Unit"])
        bq = display_to_base(qty, unit, row["Unit Type"])
        total = round(bq*cpu,6)
        entry = {"Ingredient":ing,"Quantity":bq,"Cost per Unit":cpu,"Total Cost":total,"Input Unit":unit}
        st.session_state.meal_ingredients = pd.concat([
            st.session_state.meal_ingredients, pd.DataFrame([entry])
        ], ignore_index=True)
        st.success(f"Added {qty}{unit} of {ing}")

    # Save meal callback
    def save_callback():
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
        # Reset state
        st.session_state.meal_name = ""
        st.session_state.meal_ingredients = pd.DataFrame(columns=df_ing.columns)
        st.session_state.new_qty = 0.0
        st.session_state.new_unit = None

    # UI: New Meal
    st.subheader("Create / Add Meal")
    c1,c2,c3,c4 = st.columns([3,2,2,1])
    with c1:
        st.text_input("Meal Name", key="meal_name")
    with c2:
        st.selectbox("Ingredient", options, key="new_ing", on_change=reset_unit)
    with c3:
        info = ingredients_df[ingredients_df["Ingredient"].str.lower()==st.session_state.new_ing.lower()]
        base = info.iloc[0]["Unit Type"] if not info.empty else "unit"
        opts = get_display_unit_options(base)
        st.number_input("Qty", min_value=0.0, step=0.1, key="new_qty")
        st.selectbox("Unit", opts, key="new_unit")
    with c4:
        st.button("➕ Add Ingredient", on_click=add_callback)

    # Display unsaved
    if not st.session_state.meal_ingredients.empty:
        st.markdown(f"**Ingredients for '{st.session_state.meal_name}'**")
        temp = st.session_state.meal_ingredients.copy()
        temp["Display"] = temp.apply(
            lambda r: f"{base_to_display(r['Quantity'], ingredients_df[ingredients_df['Ingredient']==r['Ingredient']].iloc[0]['Unit Type'])[0]:.2f} {r['Input Unit']}", axis=1)
        st.dataframe(temp[["Ingredient","Display","Cost per Unit","Total Cost"]], use_container_width=True)
        st.button("💾 Save Meal", on_click=save_callback)

    # UI: List & Edit Meals
    st.markdown("---")
    st.subheader("Saved Meals")
    if not meals_df.empty:
        for meal in sorted(meals_df['Meal'].unique()):
            cols = st.columns([6,1])
            cols[0].markdown(f"**{meal}**")
            if cols[1].button("✏️", key=f"edit_{meal}"):
                st.session_state.editing_meal = meal
    else:
        st.write("No meals saved yet.")

    # Edit existing meal omitted for brevity, can be added similarly.
