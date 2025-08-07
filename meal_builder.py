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
    if t == "KG":
        return ["kg", "g"]
    if t == "L":
        return ["L", "ml"]
    return ["unit"]

# Data loaders

def load_meals():
    if os.path.exists(MEAL_DATA_PATH):
        df = pd.read_csv(MEAL_DATA_PATH)
        df.columns = df.columns.str.strip()
        if "Sell Price" not in df.columns:
            df["Sell Price"] = 0.0
        return df
    return pd.DataFrame(columns=[
        "Meal","Ingredient","Quantity","Cost Per Unit",
        "Total Cost","Input Unit","Sell Price"
    ])

def load_ingredients():
    if os.path.exists(INGREDIENTS_PATH):
        df = pd.read_csv(INGREDIENTS_PATH)
        df.columns = df.columns.str.strip().str.title()
        if "Cost Per Unit" not in df.columns:
            df["Cost Per Unit"] = df.apply(
                lambda r: round(float(r["Cost"])/float(r["Purchase Size"]),6)
                if float(r["Purchase Size"]) else 0, axis=1
            )
        df["Ingredient"] = df["Ingredient"].astype(str).str.strip().str.title()
        df["Unit Type"]  = df.get("Unit Type","unit").astype(str).str.strip().str.upper()
        return df
    return pd.DataFrame(columns=[
        "Ingredient","Unit Type","Purchase Size","Cost","Cost Per Unit"
    ])

# GitHub helper

def commit_file_to_github(local_path, repo_path, msg):
    try:
        token  = st.secrets["github_token"]
        repo   = st.secrets["github_repo"]
        branch = st.secrets.get("github_branch","main")
    except:
        return
    url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    headers = {"Authorization": f"Bearer {token}",
               "Accept": "application/vnd.github+json"}
    with open(local_path,"rb") as f:
        content = base64.b64encode(f.read()).decode()
    resp = requests.get(url, headers=headers, params={"ref":branch})
    sha  = resp.json().get("sha") if resp.status_code==200 else None
    payload = {"message": f"{msg} {datetime.utcnow().isoformat()}Z",
               "content": content,
               "branch": branch}
    if sha:
        payload["sha"] = sha
    put = requests.put(url, headers=headers, json=payload)
    if put.status_code not in (200,201):
        st.error(f"GitHub commit failed: {put.status_code}")

# Callbacks for New Meal

def add_temp():
    ing_df = load_ingredients()
    sel    = st.session_state["new_ing"]
    row    = ing_df[ing_df["Ingredient"] == sel].iloc[0]
    qty    = st.session_state["new_qty"]
    base_q = display_to_base(qty, st.session_state["new_unit"], row["Unit Type"])
    cpu    = float(row["Cost Per Unit"])
    total  = round(base_q * cpu, 6)
    entry = {
        "Ingredient":      sel,
        "Quantity":        base_q,
        "Cost Per Unit":   cpu,
        "Total Cost":      total,
        "Input Unit":      st.session_state["new_unit"]
    }
    st.session_state["meal_ingredients"] = pd.concat([
        st.session_state["meal_ingredients"],
        pd.DataFrame([entry])
    ], ignore_index=True)

    # Clear just the ingredient & quantity—leave new_unit as-is
    st.session_state["new_ing"] = ""
    st.session_state["new_qty"] = 0.0

def save_new_meal():
    mdf  = load_meals()
    temp = st.session_state["meal_ingredients"].copy()
    name = st.session_state["meal_name"].strip()
    temp["Meal"]       = name
    temp["Sell Price"] = st.session_state["meal_sell_price"]
    out  = pd.concat([mdf, temp], ignore_index=True)
    os.makedirs(os.path.dirname(MEAL_DATA_PATH), exist_ok=True)
    out.to_csv(MEAL_DATA_PATH, index=False)
    commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Update meals")
    st.success("✅ Meal saved!")

    # Reset form state
    st.session_state["meal_ingredients"] = pd.DataFrame(
        columns=["Ingredient","Quantity","Cost Per Unit","Total Cost","Input Unit"]
    )
    st.session_state["meal_form_key"]     = str(uuid.uuid4())

    # ← New: rerun to stay on the Meals tab
    st.rerun()

# Callback for Edit Meal

def add_edit_callback(mn):
    df_edit = st.session_state[f"edit_{mn}"]
    ing_df  = load_ingredients()
    sel     = st.session_state[f"new_ing_edit_{mn}"]
    row2    = ing_df[ing_df["Ingredient"] == sel].iloc[0]
    amt     = st.session_state[f"new_qty_edit_{mn}"]
    base_q2 = display_to_base(amt, st.session_state[f"new_unit_edit_{mn}"], row2["Unit Type"])
    cpu2    = float(row2["Cost Per Unit"])
    tot2    = round(base_q2 * cpu2, 6)
    newrow = {
        "Ingredient":    sel,
        "Quantity":      base_q2,
        "Cost Per Unit": cpu2,
        "Total Cost":    tot2,
        "Input Unit":    st.session_state[f"new_unit_edit_{mn}"]
    }
    st.session_state[f"edit_{mn}"] = pd.concat(
        [df_edit, pd.DataFrame([newrow])],
        ignore_index=True
    )
    st.session_state[f"edit_form_key_{mn}"] = str(uuid.uuid4())

# Main UI

def render():
    st.header("🍽️ Meal Builder")
    st.info("Build meals by adding ingredients & set a sell price; then save and edit meals.")

    meals_df = load_meals()
    ing_df   = load_ingredients()
    opts     = sorted(ing_df["Ingredient"].unique())

    # Seed new_unit so the unit dropdown is correct immediately
    if opts:
        first_ut = ing_df.loc[ing_df["Ingredient"] == opts[0], "Unit Type"].iloc[0]
    else:
        first_ut = "unit"
    st.session_state.setdefault("new_unit", get_display_unit_options(first_ut)[0])

    st.session_state.setdefault("meal_name","")
    st.session_state.setdefault("meal_sell_price",0.0)
    st.session_state.setdefault("meal_ingredients", pd.DataFrame(
        columns=["Ingredient","Quantity","Cost Per Unit","Total Cost","Input Unit"]
    ))
    st.session_state.setdefault("meal_form_key", str(uuid.uuid4()))
    st.session_state.setdefault("editing_meal", None)

    # New meal form
    with st.form(key=st.session_state["meal_form_key"]):
        c1, c2 = st.columns([3,2])
        c1.text_input("Meal Name", key="meal_name")
        c2.number_input("Sell Price", min_value=0.0, step=0.01, key="meal_sell_price")

        d1, d2, d3, d4 = st.columns([3,2,2,1])
        d1.selectbox("Ingredient", opts, key="new_ing")
        d2.number_input("Qty/Amt", min_value=0.0, step=0.1, key="new_qty")
        base = ing_df[ing_df["Ingredient"] == st.session_state["new_ing"]]
        unit_type = base.iloc[0]["Unit Type"] if not base.empty else first_ut
        uopts      = get_display_unit_options(unit_type)
        d3.selectbox("Unit", uopts, key="new_unit")
        d4.form_submit_button("➕ Add Ingredient", on_click=add_temp)
        c1.form_submit_button("💾 Save Meal",     on_click=save_new_meal)

    # Preview unsaved
    if not st.session_state["meal_ingredients"].empty:
        st.subheader(f"🧾 Ingredients for '{st.session_state['meal_name']}' (unsaved)")
        df = st.session_state["meal_ingredients"].copy()
        df["Display"] = df.apply(
            lambda r: f"{base_to_display(r['Quantity'], r['Input Unit'])[0]:.2f} {r['Input Unit']}",
            axis=1
        )
        st.dataframe(df[["Ingredient","Display","Cost Per Unit","Total Cost"]],
                     use_container_width=True)

    st.markdown("---")
    st.subheader("📦 Saved Meals")

    for mn in meals_df["Meal"].unique():
        if st.session_state["editing_meal"] != mn:
            if st.button(f"✏️ {mn}", key=f"btn_{mn}"):
                st.session_state["editing_meal"] = mn
                st.session_state[f"edit_{mn}"]   = (
                    meals_df[meals_df["Meal"] == mn]
                    .reset_index(drop=True)
                )
                st.session_state.setdefault(f"edit_form_key_{mn}", str(uuid.uuid4()))
        else:
            df_edit = st.session_state[f"edit_{mn}"]
            exp     = st.expander(f"Edit Meal {mn}", expanded=True)
            with exp:
                # Delete
                if st.button("🗑️ Delete Meal", key=f"del_{mn}"):
                    remaining = meals_df[meals_df["Meal"] != mn]
                    os.makedirs(os.path.dirname(MEAL_DATA_PATH), exist_ok=True)
                    remaining.to_csv(MEAL_DATA_PATH, index=False)
                    commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Delete meal")
                    st.success(f"Deleted {mn}")
                    st.session_state["editing_meal"] = None
                    st.rerun()

                # Rename & price
                nm = st.text_input("Meal Name", value=mn, key=f"rename_{mn}")
                pr = st.number_input(
                    "Sell Price", min_value=0.0, step=0.01,
                    value=float(
                        meals_df.loc[meals_df["Meal"]==mn, "Sell Price"].iloc[0]
                    ),
                    key=f"sellprice_{mn}"
                )

                st.markdown("### Ingredients")
                for idx, r in df_edit.iterrows():
                    cols = st.columns([3,2,2,1,1])
                    cols[0].write(r["Ingredient"])
                    qty_val, _ = base_to_display(r["Quantity"], r["Input Unit"])
                    cols[1].number_input(
                        "Qty", value=qty_val, min_value=0.0, step=0.1,
                        key=f"qty_{mn}_{idx}"
                    )

                    base_type = ing_df.loc[
                        ing_df["Ingredient"] == r["Ingredient"], "Unit Type"
                    ].iloc[0]
                    unit_opts = get_display_unit_options(base_type)
                    curr      = r["Input Unit"]
                    idx_opt   = unit_opts.index(curr) if curr in unit_opts else 0
                    cols[2].selectbox("Unit", unit_opts, index=idx_opt,
                                      key=f"unit_{mn}_{idx}")

                    cpu_exist = r.get("Cost Per Unit") or 0.0
                    bq2       = display_to_base(qty_val, curr, base_type)
                    tot2      = round(bq2 * float(cpu_exist), 6)
                    cols[3].write(f"Cost: ${tot2}")

                    if cols[4].button("Remove", key=f"rem_{mn}_{idx}"):
                        df_edit = df_edit.drop(idx).reset_index(drop=True)
                        st.session_state[f"edit_{mn}"] = df_edit
                        st.rerun()

                st.markdown("### Add Ingredient")
                with st.form(key=st.session_state[f"edit_form_key_{mn}"]):
                    a1, a2, a3 = st.columns([3,2,2])
                    a1.selectbox("Ingredient", opts, key=f"new_ing_edit_{mn}")
                    a2.number_input("Qty", min_value=0.0, step=0.1,
                                    key=f"new_qty_edit_{mn}")
                    base2 = ing_df[ing_df["Ingredient"]==
                                   st.session_state[f"new_ing_edit_{mn}"]]
                    u2 = (get_display_unit_options(base2.iloc[0]["Unit Type"])
                          if not base2.empty else ["unit"])
                    a3.selectbox("Unit", u2, key=f"new_unit_edit_{mn}")
                    st.form_submit_button("➕ Add Ingredient",
                                         on_click=add_edit_callback,
                                         args=(mn,))

                if st.button("💾 Save Changes", key=f"sv_{mn}"):
                    df_edit = st.session_state[f"edit_{mn}"]
                    df_edit["Meal"]       = nm.strip() or mn
                    df_edit["Sell Price"] = pr
                    others = meals_df[meals_df["Meal"] != mn]
                    out    = pd.concat([others, df_edit], ignore_index=True)
                    os.makedirs(os.path.dirname(MEAL_DATA_PATH), exist_ok=True)
                    out.to_csv(MEAL_DATA_PATH, index=False)
                    commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv",
                                          "Save edited meal")
                    st.success(f"✅ Saved {df_edit['Meal'].iloc[0]}")
                    st.session_state["editing_meal"] = None
                    st.rerun()

if __name__ == "__main__":
    render()
