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
        if "Sell Price" not in df.columns:
            df["Sell Price"] = 0.0
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
    meals_df = load_meals()
    df_new = st.session_state.get("meal_ingredients", pd.DataFrame())
    df_new["Meal"] = st.session_state.get("meal_name","" ).strip()
    df_new["Sell Price"] = st.session_state.get("meal_sell_price", 0.0)
    combined = pd.concat([meals_df, df_new], ignore_index=True)
    os.makedirs(os.path.dirname(MEAL_DATA_PATH), exist_ok=True)
    combined.to_csv(MEAL_DATA_PATH, index=False)
    commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Update meals")
    st.success("✅ Meal saved!")
    # clear pending ingredients only
    st.session_state["meal_ingredients"] = pd.DataFrame(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"])
    # keep meal_name and meal_sell_price for next meal
    st.session_state["meal_form_key"] = str(uuid.uuid4())

# ----------------------
# Main render
# ----------------------
def render():
    st.header("🍽️ Meal Builder")
    st.info("Build meals by adding ingredients and set a sell price; then save and edit meals.")

    meals_df = load_meals()
    ingredients_df = load_ingredients()
    options = sorted(ingredients_df["Ingredient"].unique())

    st.session_state.setdefault("meal_name", "")
    st.session_state.setdefault("meal_sell_price", 0.0)
    st.session_state.setdefault(
        "meal_ingredients",
        pd.DataFrame(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"])
    )
    st.session_state.setdefault("meal_form_key", str(uuid.uuid4()))
    st.session_state.setdefault("editing_meal", None)

    with st.form(key=st.session_state["meal_form_key"]):
        r1c1, r1c2 = st.columns([3,2])
        r1c1.text_input("Meal Name", key="meal_name")
        r1c2.number_input("Sell Price", min_value=0.0, step=0.01, key="meal_sell_price")

        r2c1, r2c2, r2c3, r2c4 = st.columns([3,2,2,1])
        r2c1.selectbox("Ingredient", options, key="new_ing")
        r2c2.number_input("Qty/Amt", min_value=0.0, step=0.1, key="new_qty")
        base = ingredients_df.loc[ingredients_df["Ingredient"]==st.session_state.get("new_ing","")]
        unit_opts = get_display_unit_options(base.iloc[0]["Unit Type"]) if not base.empty else ["unit"]
        r2c3.selectbox("Unit", unit_opts, key="new_unit")
        add_pressed = r2c4.form_submit_button("➕ Add Ingredient")
        if add_pressed:
            if not st.session_state["meal_name"].strip():
                st.warning("Enter a meal name first.")
            elif st.session_state["new_qty"] <= 0:
                st.warning("Quantity must be > 0.")
            else:
                add_callback()

        save_pressed = st.form_submit_button("💾 Save Meal")
        if save_pressed:
            if st.session_state["meal_ingredients"].empty:
                st.warning("Add at least one ingredient before saving.")
            else:
                save_callback()

    if not st.session_state["meal_ingredients"].empty:
        st.subheader(f"🧾 Ingredients for '{st.session_state['meal_name']}' (unsaved)")
        display_df = st.session_state["meal_ingredients"].copy()
        display_df["Display"] = display_df.apply(
            lambda r: f"{base_to_display(r['Quantity'], r['Input Unit'])[0]:.2f} {r['Input Unit']}", axis=1
        )
        st.dataframe(display_df[["Ingredient","Display","Cost per Unit","Total Cost"]], use_container_width=True)

    st.markdown("---")
    st.subheader("📦 Saved Meals")
    for mn in meals_df['Meal'].unique():
        key_btn = f"btn_{mn}"
        if st.session_state.get("editing_meal") != mn:
            if st.button(f"✏️ {mn}", key=key_btn):
                st.session_state["editing_meal"] = mn
                st.session_state[f"edit_{mn}"] = meals_df[meals_df['Meal']==mn].reset_index(drop=True)
                st.experimental_rerun()
        else:
            df_edit = st.session_state[f"edit_{mn}"]
            exp = st.expander(f"Edit {mn}", expanded=True)
            with exp:
                new_name = st.text_input("Meal Name", value=mn, key=f"rename_{mn}")
                orig_price = df_edit['Sell Price'].iloc[0]
                new_price = st.number_input("Sell Price", min_value=0.0, step=0.01, value=float(orig_price), key=f"sellprice_{mn}")
                for idx, r in df_edit.iterrows():
                    cols = st.columns([3,2,2,1,1])
                    cols[0].write(r['Ingredient'])
                    qty = cols[1].number_input(
                        "Qty", value=base_to_display(r['Quantity'], r['Input Unit'])[0], min_value=0.0, step=0.1, key=f"qty_{mn}_{idx}")
                    unit_sel = cols[2].selectbox(
                        "Unit", get_display_unit_options(r['Input Unit']), index=get_display_unit_options(r['Input Unit']).index(r['Input Unit']), key=f"unit_{mn}_{idx}")
                    bq = display_to_base(qty, unit_sel, r['Input Unit'])
                    cpu = float(r['Cost per Unit'])
                    total = round(bq*cpu,6)
                    cols[3].write(f"Cost: ${total}")
                    if cols[4].button("Remove", key=f"rem_{mn}_{idx}"):
                        df_edit = df_edit.drop(idx).reset_index(drop=True)
                        st.session_state[f"edit_{mn}"] = df_edit
                        st.experimental_rerun()
                if st.button("💾 Save Changes", key=f"sv_{mn}"):
                    final = st.session_state[f"edit_{mn}"]
                    final['Meal'] = st.session_state[f"rename_{mn}"].strip() or mn
                    final['Sell Price'] = st.session_state[f"sellprice_{mn}"]
                    others = meals_df[meals_df['Meal'] != mn]
                    out = pd.concat([others, final], ignore_index=True)
                    os.makedirs(os.path.dirname(MEAL_DATA_PATH), exist_ok=True)
                    out.to_csv(MEAL_DATA_PATH, index=False)
                    commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Save edited meal")
                    st.success(f"✅ Saved {final['Meal'].iloc[0]}")
                    del st.session_state[f"edit_{mn}"]
                    st.session_state["editing_meal"] = None
