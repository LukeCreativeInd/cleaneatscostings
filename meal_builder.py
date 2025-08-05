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
    return pd.DataFrame(columns=["Meal", "Ingredient", "Quantity", "Cost per Unit", "Total Cost", "Input Unit"])


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
    st.info(
        """
Build meals by adding ingredients with quantities.
You can add, save, view, and edit meals with a clean interface.
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
        pd.DataFrame(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"]),
    )
    st.session_state.setdefault("new_meal_qty", 0.0)
    st.session_state.setdefault("new_meal_unit", None)
    if "new_meal_ingredient" not in st.session_state:
        st.session_state.new_meal_ingredient = ingredient_options[0] if ingredient_options else ""

    # Callback: reset unit when ingredient changes
    def reset_unit():
        sel = st.session_state.new_meal_ingredient
        info = ingredients_df[ingredients_df["Ingredient"].str.lower()==sel.lower()]
        base = info.iloc[0]["Unit Type"] if not info.empty else ""
        opts = get_display_unit_options(base)
        st.session_state.new_meal_unit = opts[0] if opts else None

    # Callback: save meal
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
        # Reset state before rerun
        st.session_state.meal_name = ""
        st.session_state.meal_ingredients = pd.DataFrame(columns=entries.columns)
        st.session_state.new_meal_qty = 0.0
        st.session_state.new_meal_unit = None

    # UI: Add Ingredient Form
    st.subheader("Create / Add Meal")
    with st.form("new_meal_form", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns([3,2,2,1])
        with c1:
            st.text_input("Meal Name", key="meal_name")
        with c2:
            st.selectbox(
                "Ingredient", ingredient_options,
                key="new_meal_ingredient",
                on_change=reset_unit,
            )
        with c3:
            sel = st.session_state.new_meal_ingredient
            info = ingredients_df[ingredients_df["Ingredient"].str.lower()==sel.lower()]
            base_unit = info.iloc[0]["Unit Type"] if not info.empty else ""
            opts = get_display_unit_options(base_unit)
            st.number_input("Qty", min_value=0.0, step=0.1, key="new_meal_qty")
            st.selectbox("Unit", opts, key="new_meal_unit")
        with c4:
            submitted = st.form_submit_button("➕ Add Ingredient")
        if submitted:
            name = st.session_state.meal_name.strip()
            if not name:
                st.warning("Enter meal name first.")
            else:
                qty = st.session_state.new_meal_qty
                unit = st.session_state.new_meal_unit
                if qty <= 0:
                    st.warning("Quantity must be >0.")
                else:
                    row = info.iloc[0]
                    cpu = float(row["Cost Per Unit"])
                    base_qty = display_to_base(qty, unit, row.get("Unit Type",""))
                    total = round(base_qty * cpu, 6)
                    entry = {
                        "Ingredient": row["Ingredient"],
                        "Quantity": base_qty,
                        "Cost per Unit": cpu,
                        "Total Cost": total,
                        "Input Unit": unit,
                    }
                    st.session_state.meal_ingredients = pd.concat(
                        [st.session_state.meal_ingredients, pd.DataFrame([entry])],
                        ignore_index=True,
                    )
                    st.success(f"Added {qty}{unit} of {row['Ingredient']}")

    # UI: Display Unsaved Ingredients + Save Button
    if not st.session_state.meal_ingredients.empty:
        st.subheader(f"🧾 Ingredients for '{st.session_state.meal_name}' (unsaved)")
        temp = st.session_state.meal_ingredients.copy()
        temp["Display"] = temp.apply(
            lambda r: f"{base_to_display(r['Quantity'],
                ingredients_df[ingredients_df['Ingredient']==r['Ingredient']].iloc[0]['Unit Type'])[0]:.2f} {r['Input Unit']}",
            axis=1,
        )
        st.dataframe(temp[["Ingredient","Display","Cost per Unit","Total Cost"]], use_container_width=True)
        st.button("💾 Save Meal", on_click=save_meal_callback)

    # UI: List and Edit Saved Meals
    st.markdown("---")
    st.subheader("📦 Saved Meals")
    if not meals_df.empty:
        for meal in sorted(meals_df['Meal'].unique()):
            cols = st.columns([6,1])
            cols[0].markdown(f"**{meal}**")
            if cols[1].button("✏️", key=f"edit_{meal}"):
                st.session_state.editing_meal = meal
    else:
        st.write("No meals saved yet.")

    # UI: Edit Existing Meal
    if st.session_state.get("editing_meal"):
        mn = st.session_state.editing_meal
        edit_key = f"edit_{mn}_df"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = meals_df[meals_df['Meal']==mn].reset_index(drop=True)
        df_edit = st.session_state[edit_key]
        try:
            modal = st.modal(f"Edit Meal: {mn}", key=f"modal_{mn}")
        except:
            modal = st.expander(f"Edit Meal: {mn}", expanded=True)
        with modal:
            # Rename / Delete
            new_name = st.text_input("Meal Name", value=mn, key=f"rename_{mn}")
            if st.button("🗑️ Delete Meal", key=f"del_{mn}"):
                remaining = meals_df[meals_df['Meal']!=mn]
                remaining.to_csv(MEAL_DATA_PATH, index=False)
                commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Delete meal")
                st.success(f"Deleted {mn}")
                st.session_state.pop(edit_key, None)
                st.session_state.pop("editing_meal", None)
                st.experimental_rerun()

            # Edit ingredients
            st.markdown("### Ingredients")
            updated = []
            for idx, r in df_edit.iterrows():
                ing = r['Ingredient']
                base = float(r['Quantity'])
                cpu = float(r['Cost per Unit'])
                iu = r.get('Input Unit', None)
                info = ingredients_df[ingredients_df['Ingredient']==ing].iloc[0]
                bu = info['Unit Type']
                dq, du = base_to_display(base, bu)
                if iu: du = iu
                col1, col2, col3, col4, col5 = st.columns([3,2,2,2,1])
                col1.markdown(f"**{ing}**")
                uq = col2.number_input(f"qty_{mn}_{idx}", value=float(dq), key=f"uq_{mn}_{idx}", label_visibility='collapsed')
                uopts = get_display_unit_options(bu)
                uu = col3.selectbox(f"unit_{mn}_{idx}", options=uopts, index=uopts.index(du) if du in uopts else 0, key=f"uu_{mn}_{idx}", label_visibility='collapsed')
                bq = display_to_base(uq, uu, bu)
                totq = round(bq*cpu,6)
                col4.markdown(f"Cost: ${totq:.2f}")
                if col5.button("Remove", key=f"rm_{mn}_{idx}"):
                    st.info(f"Removed {ing}")
                updated.append({'Ingredient':ing,'Quantity':bq,'Cost per Unit':cpu,'Total Cost':totq,'Input Unit':uu})

            # Add new ingredient
            st.markdown("#### Add Ingredient")
            a1,a2,a3,a4 = st.columns([3,2,2,1])
            with a1:
                ai = a1.selectbox("", ingredient_options, key=f"agi_{mn}", label_visibility='collapsed')
            with a2:
                info2 = ingredients_df[ingredients_df['Ingredient']==ai].iloc[0]
                bu2 = info2['Unit Type']
                aq = a2.number_input("", min_value=0.0, step=0.1, key=f"aq_{mn}", label_visibility='collapsed')
            with a3:
                uo2 = get_display_unit_options(bu2)
                au = a3.selectbox("", uo2, key=f"au_{mn}", label_visibility='collapsed')
            with a4:
                if a4.button("+", key=f"addit_{mn}") and aq>0:
                    cpu2 = float(info2['Cost Per Unit'])
                    bq2 = display_to_base(aq, au, bu2)
                    tot2 = round(bq2*cpu2,6)
                    updated.append({'Ingredient':ai,'Quantity':bq2,'Cost per Unit':cpu2,'Total Cost':tot2,'Input Unit':au})
                    st.success(f"Added {aq}{au} of {ai}")

            # Save edits
            if st.button("💾 Save Changes", key=f"sv_{mn}"):
                final_name = new_name.strip() or mn
                df_updated = pd.DataFrame(updated)
                df_updated.insert(0,'Meal',final_name)
                others = meals_df[meals_df['Meal']!=mn]
                final = pd.concat([others, df_updated], ignore_index=True)
                final.to_csv(MEAL_DATA_PATH, index=False)
                commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Update meals")
                st.success(f"Updated {final_name}")
                st.session_state.pop(edit_key, None)
                st.session_state.pop("editing_meal", None)
                st.experimental_rerun()
