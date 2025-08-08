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
        "Total Cost","Input Unit","Unit Type","Sell Price"
    ])

def load_ingredients():
    if os.path.exists(INGREDIENTS_PATH):
        df = pd.read_csv(INGREDIENTS_PATH)
        df.columns = df.columns.str.strip().str.title()
        if "Cost Per Unit" not in df.columns:
            df["Cost Per Unit"] = df.apply(
                lambda r: round(float(r["Cost"]) / float(r["Purchase Size"]), 6)
                if float(r["Purchase Size"]) else 0,
                axis=1
            )
        df["Ingredient"] = df["Ingredient"].astype(str).str.strip().str.title()
        df["Unit Type"] = df.get("Unit Type","unit").astype(str).str.strip().str.upper()
        return df
    return pd.DataFrame(columns=[
        "Ingredient","Unit Type","Purchase Size","Cost","Cost Per Unit"
    ])

# GitHub helper

def commit_file_to_github(local_path, repo_path, msg):
    try:
        token = st.secrets["github_token"]
        repo  = st.secrets["github_repo"]
        branch = st.secrets.get("github_branch","main")
    except:
        return
    url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    resp = requests.get(url, headers=headers, params={"ref": branch})
    sha  = resp.json().get("sha") if resp.status_code == 200 else None
    payload = {
        "message": f"{msg} {datetime.utcnow().isoformat()}Z",
        "content": content,
        "branch": branch
    }
    if sha:
        payload["sha"] = sha
    put = requests.put(url, headers=headers, json=payload)
    if put.status_code not in (200,201):
        st.error(f"GitHub commit failed: {put.status_code}")

# New-meal callbacks

def add_temp():
    ing_df = load_ingredients()
    sel    = st.session_state["new_ing"]
    row    = ing_df[ing_df["Ingredient"] == sel].iloc[0]
    qty    = st.session_state["new_qty"]
    base_q = display_to_base(qty, st.session_state["new_unit"], row["Unit Type"])
    cpu    = float(row["Cost Per Unit"])
    total  = round(base_q * cpu, 6)
    entry = {
        "Ingredient":    sel,
        "Quantity":      base_q,
        "Cost Per Unit": cpu,
        "Total Cost":    total,
        "Input Unit":    st.session_state["new_unit"],
        "Unit Type":     row["Unit Type"]
    }
    st.session_state["meal_ingredients"] = pd.concat(
        [st.session_state["meal_ingredients"], pd.DataFrame([entry])],
        ignore_index=True
    )
    # Clear next run
    st.session_state["__clear_add_fields__"] = True

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

    # message + refresh list + reset draft
    st.session_state["__last_meal_save_msg__"] = "✅ Meal saved!"
    st.session_state["__meals_saved__"] = True
    st.session_state["meal_ingredients"] = pd.DataFrame(
        columns=["Ingredient","Quantity","Cost Per Unit","Total Cost","Input Unit","Unit Type"]
    )
    st.session_state["meal_form_key"] = str(uuid.uuid4())

# Edit-meal callbacks

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
        "Input Unit":    st.session_state[f"new_unit_edit_{mn}"],
        "Unit Type":     row2["Unit Type"]
    }
    st.session_state[f"edit_{mn}"] = pd.concat(
        [df_edit, pd.DataFrame([newrow])],
        ignore_index=True
    )
    st.session_state[f"edit_form_key_{mn}"] = str(uuid.uuid4())

def save_edit_meal(mn):
    df_edit = st.session_state[f"edit_{mn}"]

    # Read latest widget values
    for idx, r in df_edit.iterrows():
        qty_display = st.session_state.get(
            f"qty_{mn}_{idx}",
            base_to_display(r["Quantity"], r["Unit Type"])[0]
        )
        unit_input  = st.session_state.get(f"unit_{mn}_{idx}", r["Input Unit"])
        base_q = display_to_base(qty_display, unit_input, r["Unit Type"])
        df_edit.at[idx, "Quantity"]   = base_q
        df_edit.at[idx, "Input Unit"] = unit_input
        df_edit.at[idx, "Total Cost"] = round(base_q * float(r["Cost Per Unit"]), 6)

    nm  = st.session_state[f"rename_{mn}"].strip() or mn
    pr  = st.session_state[f"sellprice_{mn}"]
    df_edit["Meal"]       = nm
    df_edit["Sell Price"] = pr

    # Persist
    all_meals = load_meals()
    others    = all_meals[all_meals["Meal"] != mn]
    out       = pd.concat([others, df_edit], ignore_index=True)
    os.makedirs(os.path.dirname(MEAL_DATA_PATH), exist_ok=True)
    out.to_csv(MEAL_DATA_PATH, index=False)
    commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Save edited meal")

    # success + refresh + close editor
    st.session_state["__last_meal_save_msg__"] = f"✅ Saved {nm}"
    st.session_state["__meals_saved__"] = True
    st.session_state["editing_meal"] = None

# Main UI

def render():
    st.header("🍽️ Meal Builder")
    st.info("Build meals by adding ingredients & set a sell price; then save and edit meals.")

    # success message (one-shot)
    msg = st.session_state.pop("__last_meal_save_msg__", None)
    if msg:
        st.success(msg)

    meals_df = load_meals()
    ing_df   = load_ingredients()
    opts     = sorted(ing_df["Ingredient"].unique())

    # seed new_unit
    if opts:
        first_ut = ing_df.loc[ing_df["Ingredient"] == opts[0], "Unit Type"].iloc[0]
    else:
        first_ut = "unit"
    st.session_state.setdefault("new_unit", get_display_unit_options(first_ut)[0])

    st.session_state.setdefault("meal_name","")
    st.session_state.setdefault("meal_sell_price",0.0)
    st.session_state.setdefault("meal_ingredients", pd.DataFrame(
        columns=["Ingredient","Quantity","Cost Per Unit","Total Cost","Input Unit","Unit Type"]
    ))
    st.session_state.setdefault("meal_form_key", str(uuid.uuid4()))
    st.session_state.setdefault("editing_meal", None)

    # Clear new-ingredient fields before building widgets
    if st.session_state.pop("__clear_add_fields__", False):
        st.session_state["new_qty"] = 0.0

    # New meal form
    with st.form(key=st.session_state["meal_form_key"]):
        c1, c2 = st.columns([3,2])
        c1.text_input("Meal Name", key="meal_name")
        c2.number_input("Sell Price", min_value=0.0, step=0.01, key="meal_sell_price")

        d1, d2, d3, d4 = st.columns([3,2,2,1])
        d1.selectbox("Ingredient", opts, key="new_ing")
        d2.number_input("Qty/Amt", min_value=0.0, step=0.1, key="new_qty")
        base = ing_df[ing_df["Ingredient"] == st.session_state["new_ing"]]
        ut   = base.iloc[0]["Unit Type"] if not base.empty else first_ut
        uopts= get_display_unit_options(ut)
        d3.selectbox("Unit", uopts, key="new_unit")

        add_clicked  = d4.form_submit_button("➕ Add Ingredient")
        save_clicked = c1.form_submit_button("💾 Save Meal")

        if add_clicked:
            if not st.session_state["meal_name"].strip():
                st.warning("Enter a meal name first.")
            elif st.session_state["new_qty"] <= 0:
                st.warning("Quantity must be > 0.")
            elif not st.session_state["new_ing"]:
                st.warning("Select an ingredient.")
            else:
                add_temp()

        if save_clicked:
            if st.session_state["meal_ingredients"].empty:
                st.warning("Add at least one ingredient before saving.")
            elif not st.session_state["meal_name"].strip():
                st.warning("Enter a meal name.")
            else:
                save_new_meal()

    # If something was saved/edited/deleted, refresh meals_df so the list updates immediately
    if st.session_state.pop("__meals_saved__", False):
        meals_df = load_meals()

    # Preview unsaved
    if not st.session_state["meal_ingredients"].empty:
        st.subheader(f"🧾 Ingredients for '{st.session_state['meal_name']}' (unsaved)")
        df = st.session_state["meal_ingredients"].copy()
        df["Display"] = df.apply(
            lambda r: f"{base_to_display(r['Quantity'], r['Unit Type'])[0]:.2f} {r['Input Unit']}",
            axis=1
        )
        st.dataframe(df[["Ingredient","Display","Cost Per Unit","Total Cost"]], use_container_width=True)

    st.markdown("---")
    st.subheader("📦 Saved Meals")

    # --- Render all edit buttons first ---
    meals = list(meals_df["Meal"].unique())
    cols = st.columns(min(3, max(1, len(meals)))) if meals else [st]
    for i, mn in enumerate(meals):
        if cols[i % len(cols)].button(f"✏️ {mn}", key=f"btn_{mn}"):
            # prepare editor state
            tmp = meals_df[meals_df["Meal"] == mn].copy().reset_index(drop=True)
            if "Unit Type" not in tmp.columns:
                tmp["Unit Type"] = tmp.apply(
                    lambda r: load_ingredients().set_index("Ingredient").loc[r["Ingredient"], "Unit Type"], axis=1
                )
            st.session_state[f"edit_{mn}"] = tmp
            st.session_state.setdefault(f"edit_form_key_{mn}", str(uuid.uuid4()))
            st.session_state["editing_meal"] = mn

    # --- After buttons, render the active editor (if any) ---
    active = st.session_state.get("editing_meal")
    if active:
        df_edit = st.session_state.get(
            f"edit_{active}",
            meals_df[meals_df["Meal"] == active].copy().reset_index(drop=True)
        )
        exp = st.expander(f"Edit Meal {active}", expanded=True)
        with exp:
            if st.button("🗑️ Delete Meal", key=f"del_{active}"):
                remaining = meals_df[meals_df["Meal"] != active]
                os.makedirs(os.path.dirname(MEAL_DATA_PATH), exist_ok=True)
                remaining.to_csv(MEAL_DATA_PATH, index=False)
                commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Delete meal")
                st.session_state["__last_meal_save_msg__"] = f"🗑️ Deleted {active}"
                st.session_state["editing_meal"] = None
                st.session_state["__meals_saved__"] = True
                return

            nm = st.text_input("Meal Name", value=active, key=f"rename_{active}")
            pr = st.number_input(
                "Sell Price", min_value=0.0, step=0.01,
                value=float(meals_df.loc[meals_df["Meal"] == active, "Sell Price"].iloc[0]),
                key=f"sellprice_{active}"
            )

            st.markdown("### Ingredients")
            for idx, r in df_edit.iterrows():
                cols_row = st.columns([3, 2, 2, 1, 1])
                cols_row[0].write(r["Ingredient"])
                qty_val, _ = base_to_display(r["Quantity"], r["Unit Type"])
                cols_row[1].number_input(
                    "Qty", value=qty_val, min_value=0.0, step=0.1, key=f"qty_{active}_{idx}"
                )
                unit_opts = get_display_unit_options(r["Unit Type"])
                cols_row[2].selectbox(
                    "Unit", unit_opts, index=unit_opts.index(r["Input Unit"]), key=f"unit_{active}_{idx}"
                )
                bq2 = display_to_base(qty_val, r["Input Unit"], r["Unit Type"])
                tot2 = round(bq2 * float(r["Cost Per Unit"]), 6)
                cols_row[3].write(f"Cost: ${tot2}")
                if cols_row[4].button("Remove", key=f"rem_{active}_{idx}"):
                    df2 = df_edit.drop(idx).reset_index(drop=True)
                    st.session_state[f"edit_{active}"] = df2
                    return

            st.markdown("### Add Ingredient")
            with st.form(key=st.session_state[f"edit_form_key_{active}"]):
                a1, a2, a3 = st.columns([3, 2, 2])
                a1.selectbox("Ingredient", opts, key=f"new_ing_edit_{active}")
                a2.number_input("Qty", min_value=0.0, step=0.1, key=f"new_qty_edit_{active}")
                b2 = load_ingredients()[load_ingredients()["Ingredient"] == st.session_state[f"new_ing_edit_{active}"]]
                u2 = get_display_unit_options(b2.iloc[0]["Unit Type"]) if not b2.empty else ["unit"]
                a3.selectbox("Unit", u2, key=f"new_unit_edit_{active}")
                if st.form_submit_button("➕ Add Ingredient"):
                    if not st.session_state[f"new_ing_edit_{active}"]:
                        st.warning("Select an ingredient.")
                    elif st.session_state[f"new_qty_edit_{active}"] <= 0:
                        st.warning("Quantity must be > 0.")
                    else:
                        add_edit_callback(active)

            # Save button in normal flow (not on_click)
            if st.button("💾 Save Changes", key=f"sv_{active}"):
                save_edit_meal(active)

if __name__ == "__main__":
    render()
