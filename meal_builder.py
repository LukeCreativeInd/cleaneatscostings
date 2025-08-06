import streamlit as st
import pandas as pd
import os
import requests
import base64
import uuid
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
        return qty / 1000.0 if u in ["g","gram","grams"] else qty
    if t == "L":
        return qty / 1000.0 if u == "ml" else qty
    return qty


def base_to_display(qty, base_unit_type):
    t = (base_unit_type or "").upper()
    if t == "KG":
        return (qty*1000.0, "g") if qty < 1 else (qty, "kg")
    if t == "L":
        return (qty*1000.0, "ml") if qty < 1 else (qty, "L")
    return (qty, "unit")


def get_display_unit_options(base_unit_type):
    t = (base_unit_type or "").upper()
    if t == "KG": return ["kg","g"]
    if t == "L": return ["L","ml"]
    return ["unit"]

# ----------------------
# Data loaders
# ----------------------
def load_meals():
    if os.path.exists(MEAL_DATA_PATH):
        df = pd.read_csv(MEAL_DATA_PATH)
        df.columns = df.columns.str.strip()
        return df
    return pd.DataFrame(columns=["Meal","Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit","Sell Price"])


def load_ingredients():
    if os.path.exists(INGREDIENTS_PATH):
        df = pd.read_csv(INGREDIENTS_PATH)
        df.columns = df.columns.str.strip().str.title()
        if "Cost Per Unit" not in df.columns:
            df["Cost Per Unit"] = df.apply(
                lambda r: round(float(r.get("Cost",0)) / float(r.get("Purchase Size",1)),6)
                if float(r.get("Purchase Size",1)) else 0,
                axis=1
            )
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
    payload = {"message":f"{message_prefix} {datetime.utcnow().isoformat()}Z","content":content,"branch":branch}
    if sha: payload["sha"] = sha
    put = requests.put(url, headers=headers, json=payload)
    if put.status_code not in (200,201): st.error(f"GitHub commit failed: {put.status_code} {put.text}")

# ----------------------
# Core rendering
# ----------------------
def render():
    st.header("🍽️ Meal Builder")
    st.info("Build meals by adding ingredients with quantities and set a sell price; then save and edit meals.")

    meals_df = load_meals()
    ingredients_df = load_ingredients()
    options = sorted(ingredients_df["Ingredient"].unique())

    # session state
    st.session_state.setdefault("meal_name","")
    st.session_state.setdefault("meal_ingredients",pd.DataFrame(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"]))
    st.session_state.setdefault("meal_form_key",str(uuid.uuid4()))

    # callbacks
    def add_ingredient():
        row = ingredients_df[ingredients_df["Ingredient"] == st.session_state["new_ing"]].iloc[0]
        qty = st.session_state["new_qty"]
        bq = display_to_base(qty, st.session_state["new_unit"], row["Unit Type"])
        cpu = float(row["Cost Per Unit"])
        total = round(bq*cpu,6)
        entry = {"Ingredient":row["Ingredient"],"Quantity":bq,"Cost per Unit":cpu,"Total Cost":total,"Input Unit":st.session_state["new_unit"]}
        st.session_state["meal_ingredients"] = pd.concat([st.session_state["meal_ingredients"],pd.DataFrame([entry])],ignore_index=True)

    def save_meal():
        # combine
        df_new = st.session_state["meal_ingredients"].copy()
        df_new["Meal"] = st.session_state["meal_name"].strip()
        df_new["Sell Price"] = st.session_state.get("meal_sell_price",0.0)
        combined = pd.concat([meals_df, df_new], ignore_index=True)
        os.makedirs("data",exist_ok=True)
        combined.to_csv(MEAL_DATA_PATH,index=False)
        commit_file_to_github(MEAL_DATA_PATH,"data/meals.csv","Update meals")
        st.success("✅ Meal saved!")
        # reset
        st.session_state["meal_ingredients"] = pd.DataFrame(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"])
        st.session_state["meal_form_key"] = str(uuid.uuid4())
        st.session_state["meal_name"] = ""
        st.session_state["meal_sell_price"] = 0.0

    # Create/Add Meal form
    form_key = st.session_state["meal_form_key"]
    with st.form(form_key):
        st.subheader("Create / Add Meal")
        c1,c2,c3,c4,c5 = st.columns([3,2,2,1,2])
        c1.text_input("Meal Name",key="meal_name")
        c2.selectbox("Ingredient", options, key="new_ing")
        c3.number_input("Qty",min_value=0.0,step=0.1,key="new_qty")
        row = ingredients_df[ingredients_df["Ingredient"] == st.session_state.get("new_ing","")]
        if not row.empty:
            unit_opts = get_display_unit_options(row.iloc[0]["Unit Type"])
        else:
            unit_opts = ["unit"]
        c3.selectbox("Unit",unit_opts,key="new_unit")
        c5.number_input("Sell Price",min_value=0.0,step=0.01,key="meal_sell_price")
        add = c4.form_submit_button("➕ Add Ingredient")
        if add:
            if not st.session_state["meal_name"].strip():
                st.warning("Enter meal name first.")
            elif st.session_state["new_qty"] <= 0:
                st.warning("Quantity must be >0.")
            else:
                add_ingredient()
        save = st.form_submit_button("💾 Save Meal")
        if save:
            if st.session_state["meal_ingredients"].empty:
                st.warning("Add at least one ingredient before saving.")
            else:
                save_meal()

    # Display unsaved ingredients
    if not st.session_state["meal_ingredients"].empty:
        st.subheader(f"🧾 Ingredients for '{st.session_state['meal_name']}' (unsaved)")
        temp = st.session_state["meal_ingredients"].copy()
        temp["Display"] = temp.apply(lambda r: f"{base_to_display(r['Quantity'],r['Input Unit'])[0]:.2f} {r['Input Unit']}",axis=1)
        st.dataframe(temp[["Ingredient","Display","Cost per Unit","Total Cost"]],use_container_width=True)

    # Edit existing meals (omitted for brevity, unchanged...)
