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
        # Ensure Sell Price column exists
        if "Sell Price" not in df.columns:
            df["Sell Price"] = 0.0
        return df
    # default schema
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
    payload = {
        "message":f"{message_prefix} {datetime.utcnow().isoformat()}Z",
        "content":content,
        "branch":branch
    }
    if sha: payload["sha"] = sha
    put = requests.put(url, headers=headers, json=payload)
    if put.status_code not in (200,201): st.error(f"GitHub commit failed: {put.status_code} {put.text}")

# ----------------------
# Callbacks
# ----------------------
def add_callback():
    # Add selected ingredient to the pending meal list
    ingredients_df = load_ingredients()
    row = ingredients_df[ingredients_df["Ingredient"]==st.session_state.get("new_ing")].iloc[0]
    qty = st.session_state.get("new_qty", 0.0)
    bq = display_to_base(qty, st.session_state.get("new_unit"), row["Unit Type"])
    cpu = float(row["Cost Per Unit"])
    total = round(bq * cpu, 6)
    entry = {
        "Ingredient": row["Ingredient"],
        "Quantity": bq,
        "Cost per Unit": cpu,
        "Total Cost": total,
        "Input Unit": st.session_state.get("new_unit")
    }
    st.session_state["meal_ingredients"] = pd.concat([
        st.session_state["meal_ingredients"],
        pd.DataFrame([entry])
    ], ignore_index=True)


def save_callback():
    # Persist the pending meal and its sell price to CSV (and GitHub)
    meals_df = load_meals()
    df_new = st.session_state.get("meal_ingredients", pd.DataFrame())
    df_new["Meal"] = st.session_state.get("meal_name","").strip()
    df_new["Sell Price"] = st.session_state.get("meal_sell_price", 0.0)
    combined = pd.concat([meals_df, df_new], ignore_index=True)
    os.makedirs(os.path.dirname(MEAL_DATA_PATH), exist_ok=True)
    combined.to_csv(MEAL_DATA_PATH, index=False)
    commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Update meals")
    st.success("✅ Meal saved!")
    # Reset form state
    st.session_state["meal_ingredients"] = pd.DataFrame(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"])
    st.session_state["meal_form_key"] = str(uuid.uuid4())
    st.session_state["meal_name"] = ""
    st.session_state["meal_sell_price"] = 0.0
    st.experimental_rerun()
