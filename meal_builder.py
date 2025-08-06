import streamlit as st
import pandas as pd
import os
import requests
import base64
import uuid
from datetime import datetime

MEAL_DATA_PATH = "data/meals.csv"
INGREDIENTS_PATH = "data/ingredients.csv"

# Utility functions

def display_to_base(qty, display_unit, base_unit_type):
    t = (base_unit_type or "").upper()
    u = (display_unit or "").lower()
    if t == "KG":
        return qty/1000.0 if u in ["g","gram","grams"] else qty
    if t == "L":
        return qty/1000.0 if u == "ml" else qty
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

# Data loaders

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
        if "Cost Per Unit" not in df.columns and "Cost" in df.columns and "Purchase Size" in df.columns:
            df["Cost Per Unit"] = df.apply(
                lambda r: round(float(r["Cost"]) / float(r["Purchase Size"]),6) if float(r["Purchase Size"]) else 0,
                axis=1)
        df["Ingredient"] = df["Ingredient"].astype(str).str.strip().str.title()
        df["Unit Type"] = df.get("Unit Type","unit").astype(str).str.strip().str.upper()
        return df
    return pd.DataFrame(columns=["Ingredient","Unit Type","Purchase Size","Cost","Cost Per Unit"])

# GitHub helper

def commit_file_to_github(local_path, repo_path, msg):
    try:
        token = st.secrets["github_token"]
        repo = st.secrets["github_repo"]
        branch = st.secrets.get("github_branch","main")
    except:
        return
    url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    resp = requests.get(url, headers=headers, params={"ref": branch})
    sha = resp.json().get("sha") if resp.status_code == 200 else None
    payload = {"message": f"{msg} {datetime.utcnow().isoformat()}Z", "content": content, "branch": branch}
    if sha:
        payload["sha"] = sha
    put = requests.put(url, headers=headers, json=payload)
    if put.status_code not in (200,201):
        st.error(f"GitHub commit failed: {put.status_code}")

# Callbacks

def add_temp():
    ing_df = load_ingredients()
    sel = st.session_state["new_ing"]
    row = ing_df[ing_df["Ingredient"] == sel].iloc[0]
    qty = st.session_state["new_qty"]
    base_qty = display_to_base(qty, st.session_state["new_unit"], row["Unit Type"])
    cpu = float(row["Cost Per Unit"])
    total = round(base_qty * cpu, 6)
    entry = {
        "Ingredient": sel,
        "Quantity": base_qty,
        "Cost per Unit": cpu,
        "Total Cost": total,
        "Input Unit": st.session_state["new_unit"]
    }
    st.session_state["meal_ingredients"] = pd.concat([
        st.session_state["meal_ingredients"], pd.DataFrame([entry])
    ], ignore_index=True)
    # clear only entry fields
    st.session_state["new_ing"] = opts[0]
    st.session_state["new_qty"] = 0.0
    st.session_state["new_unit"] = get_display_unit_options(row["Unit Type"])[0]


def save_new_meal():
    mdf = load_meals()
    temp = st.session_state["meal_ingredients"].copy()
    meal_name = st.session_state["meal_name"].strip()
    temp["Meal"] = meal_name
    temp["Sell Price"] = st.session_state["meal_sell_price"]
    out = pd.concat([mdf, temp], ignore_index=True)
    os.makedirs(os.path.dirname(MEAL_DATA_PATH), exist_ok=True)
    out.to_csv(MEAL_DATA_PATH, index=False)
    commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Update meals")
    st.success("✅ Meal saved!")
    st.session_state["meal_ingredients"] = pd.DataFrame(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"])
    # Rerun to stay on the Meals tab after saving
    st.rerun()

# Edit callback

def select_edit(meal_name):
    meals_df = load_meals()
    st.session_state["editing_meal"] = meal_name
    st.session_state[f"edit_{meal_name}"] = meals_df[meals_df['Meal'] == meal_name].reset_index(drop=True)

# Add ingredient in edit mode

def add_edit_callback(meal_name):
    ing_df = load_ingredients()
    df_edit = st.session_state[f"edit_{meal_name}"]
    key_i = f"new_ing_edit_{meal_name}"
    key_q = f"new_qty_edit_{meal_name}"
    key_u = f"new_unit_edit_{meal_name}"
    new_i = st.session_state.get(key_i)
    new_q = st.session_state.get(key_q)
    new_u = st.session_state.get(key_u)
    row2 = ing_df[ing_df['Ingredient'] == new_i].iloc[0]
    bq3 = display_to_base(new_q, new_u, row2['Unit Type'])
    tot3 = round(bq3 * float(row2['Cost Per Unit']), 6)
    newrow = {
        'Ingredient': new_i,
        'Quantity': bq3,
        'Cost per Unit': float(row2['Cost Per Unit']),
        'Total Cost': tot3,
        'Input Unit': new_u
    }
    st.session_state[f"edit_{meal_name}"] = pd.concat([df_edit, pd.DataFrame([newrow])], ignore_index=True)

# Main UI

def render():
    st.header("🍽️ Meal Builder")
    st.info("Build meals by adding ingredients & set a sell price; then save and edit meals.")

    meals_df = load_meals()
    ing_df = load_ingredients()
    global opts
    opts = sorted(ing_df["Ingredient"].unique())

    # Session state defaults
    st.session_state.setdefault("meal_name", "")
    st.session_state.setdefault("meal_sell_price", 0.0)
    st.session_state.setdefault(
        "meal_ingredients",
        pd.DataFrame(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"])
    )
    st.session_state.setdefault("new_ing", opts[0] if opts else "")
    st.session_state.setdefault("new_qty", 0.0)
    default_base = ing_df[ing_df["Ingredient"] == st.session_state["new_ing"]]
    default_units = get_display_unit_options(default_base.iloc[0]["Unit Type"]) if not default_base.empty else ["unit"]
    st.session_state.setdefault("new_unit", default_units[0])
    st.session_state.setdefault("editing_meal", None)

    # New meal form remains unchanged...
    with st.form(key="meal_form"):
        c1, c2 = st.columns([3,2])
        c1.text_input("Meal Name", key="meal_name")
        c2.number_input("Sell Price", min_value=0.0, step=0.01, key="meal_sell_price")

        d1, d2, d3, d4 = st.columns([3,2,2,1])
        d1.selectbox("Ingredient", opts, key="new_ing")
        d2.number_input("Qty/Amt", min_value=0.0, step=0.1, key="new_qty")
        base = ing_df[ing_df["Ingredient"] == st.session_state["new_ing"]]
        uopts = get_display_unit_options(base.iloc[0]["Unit Type"]) if not base.empty else ["unit"]
        d3.selectbox("Unit", uopts, key="new_unit")
        # Add ingredient with callback
        d4.form_submit_button("➕ Add Ingredient", on_click=add_temp)

        # Save meal with callback
        st.form_submit_button("💾 Save Meal", on_click=save_new_meal)

    # Preview unsaved
    if not st.session_state["meal_ingredients"].empty:
        st.subheader(f"🧾 Ingredients for '{st.session_state['meal_name']}' (unsaved)")
        df = st.session_state["meal_ingredients"].copy()
        df["Display"] = df.apply(
            lambda r: f"{base_to_display(r['Quantity'], r['Input Unit'])[0]:.2f} {r['Input Unit']}", axis=1
        )
        st.dataframe(df[["Ingredient","Display","Cost per Unit","Total Cost"]], use_container_width=True)

    st.markdown("---")
    st.subheader("📦 Saved Meals (editing below)")
    for mn in meals_df['Meal'].unique():
        if st.session_state['editing_meal'] != mn:
            st.button(f"✏️ {mn}", key=f"btn_{mn}", on_click=select_edit, args=(mn,))
        else:
            df_edit = st.session_state[f'edit_{mn}']
            exp = st.expander(f"Edit Meal {mn}", expanded=True)
            with exp:
                # Delete button
                if st.button("🗑️ Delete Meal", key=f"del_{mn}"):
                    remaining = meals_df[meals_df['Meal'] != mn]
                    os.makedirs(os.path.dirname(MEAL_DATA_PATH), exist_ok=True)
                    remaining.to_csv(MEAL_DATA_PATH, index=False)
                    commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Delete meal")
                    st.success(f"Deleted {mn}")
                    st.session_state['editing_meal'] = None
                    break
                # Rename & price
                nm = st.text_input("Meal Name", value=mn, key=f"rename_{mn}")
                pr = st.number_input("Sell Price", min_value=0.0, step=0.01,
                    value=float(meals_df.loc[meals_df['Meal']==mn, 'Sell Price'].iloc[0]), key=f"sellprice_{mn}")
                # Existing ingredients
                st.markdown("### Ingredients")
                for idx, r in df_edit.iterrows():
                    cols = st.columns([3,2,2,1,1])
                    cols[0].write(r['Ingredient'])
                    qty_val,_ = base_to_display(r['Quantity'], r['Input Unit'])
                    q = cols[1].number_input("Qty", value=qty_val, min_value=0.0, step=0.1, key=f"qty_{mn}_{idx}")
                    unit_opts = get_display_unit_options(r['Input Unit'])
                    us = cols[2].selectbox("Unit", unit_opts, index=unit_opts.index(r['Input Unit']), key=f"unit_{mn}_{idx}")
                    bq2 = display_to_base(q, us, r['Input Unit'])
                    tot2 = round(bq2 * float(r['Cost per Unit']), 6)
                    cols[3].write(f"Cost: ${tot2}")
                    if cols[4].button("Remove", key=f"rem_{mn}_{idx}"):
                        df_edit = df_edit.drop(idx).reset_index(drop=True)
                        st.session_state[f'edit_{mn}'] = df_edit
                # Add new ingredient using a dedicated form
                st.markdown("### Add Ingredient")
                with st.form(key=f"edit_form_{mn}"):
                    a1, a2, a3 = st.columns([3,2,2])
                    sel = a1.selectbox("Ingredient", opts, key=f"new_ing_edit_{mn}")
                    amt = a2.number_input("Qty", min_value=0.0, step=0.1, key=f"new_qty_edit_{mn}")
                    base2 = ing_df[ing_df['Ingredient']==sel]
                    unit_opts2 = get_display_unit_options(base2.iloc[0]['Unit Type']) if not base2.empty else ['unit']
                    uu = a3.selectbox("Unit", unit_opts2, key=f"new_unit_edit_{mn}")
                    if st.form_submit_button("➕ Add Ingredient"):
                        add_edit_callback(mn)
                        st.experimental_rerun()
                # Save edited meal
                if st.button("💾 Save Changes", key=f"sv_{mn}"):
                    df_final = st.session_state[f'edit_{mn}']
                    df_final['Meal'] = nm.strip() or mn
                    df_final['Sell Price'] = pr
                    others = meals_df[meals_df['Meal'] != mn]
                    out = pd.concat([others, df_final], ignore_index=True)
                    os.makedirs(os.path.dirname(MEAL_DATA_PATH), exist_ok=True)
                    out.to_csv(MEAL_DATA_PATH, index=False)
                    commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Save edited meal")
                    st.success(f"✅ Saved {df_final['Meal'].iloc[0]}")
                    st.session_state['editing_meal'] = None

if __name__ == "__main__":
    render()
