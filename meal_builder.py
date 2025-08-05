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
    payload = {"message":f"{message_prefix} {datetime.utcnow().isoformat()}Z","content":content,"branch":branch}
    if sha: payload["sha"] = sha
    put = requests.put(url, headers=headers, json=payload)
    if put.status_code not in (200,201): st.error(f"GitHub commit failed: {put.status_code} {put.text}")

# ----------------------
# Core rendering
# ----------------------
def render():
    st.header("🍽️ Meal Builder")
    st.info("Build meals by adding ingredients with quantities; then save and edit meals.")

    meals_df = load_meals()
    ingredients_df = load_ingredients()
    options = sorted(ingredients_df["Ingredient"].unique())

    # Session defaults for new meal
    st.session_state.setdefault("meal_name", "")
    st.session_state.setdefault(
        "meal_ingredients",
        pd.DataFrame(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"]),
    )
    st.session_state.setdefault("new_qty", 0.0)
    st.session_state.setdefault("new_ing", options[0] if options else "")
    # Determine unit options for new meal
    base0 = ingredients_df.loc[ingredients_df["Ingredient"].str.lower() == st.session_state.new_ing.lower(), "Unit Type"].iat[0] if options else "unit"
    unit_opts0 = get_display_unit_options(base0)
    if st.session_state.get("new_unit") not in unit_opts0:
        st.session_state.new_unit = unit_opts0[0]

    # Callbacks
    def add_callback():
        name = st.session_state.meal_name.strip()
        if not name:
            st.warning("Enter meal name first.")
            return
        qty = st.session_state["new_qty"]
        if qty <= 0:
            st.warning("Quantity must be >0.")
            return
        row = ingredients_df[ingredients_df["Ingredient"].str.lower() == st.session_state.new_ing.lower()].iloc[0]
        cpu = float(row["Cost Per Unit"])
        bq = display_to_base(qty, st.session_state.new_unit, row["Unit Type"])
        total = round(bq * cpu, 6)
        entry = {"Ingredient":row["Ingredient"],"Quantity":bq,"Cost per Unit":cpu,"Total Cost":total,"Input Unit":st.session_state.new_unit}
        st.session_state.meal_ingredients = pd.concat([st.session_state.meal_ingredients, pd.DataFrame([entry])], ignore_index=True)
        st.success(f"Added {qty}{st.session_state.new_unit} of {row['Ingredient']}")
        # reset
        st.session_state["new_qty"] = 0.0
        st.rerun()

    def save_callback():
        name = st.session_state.meal_name.strip()
        df_ing = st.session_state.meal_ingredients
        if not name or df_ing.empty:
            st.warning("Meal name & at least one ingredient required.")
            return
        combined = pd.concat([meals_df, df_ing.assign(Meal=name)], ignore_index=True)
        os.makedirs("data", exist_ok=True)
        combined.to_csv(MEAL_DATA_PATH, index=False)
        commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Update meals")
        st.success("✅ Meal saved!")
        # reset
        st.session_state["meal_name"] = ""
        st.session_state["meal_ingredients"] = pd.DataFrame(columns=df_ing.columns)
        st.session_state["new_qty"] = 0.0
        st.rerun()

    # UI: New Meal (wrapped in form to allow resetting)
import uuid
st.session_state.setdefault("new_meal_form_key", str(uuid.uuid4()))
form_container = st.empty()
with form_container.form(key=st.session_state["new_meal_form_key"]):
    st.subheader("Create / Add Meal")
    c1, c2, c3, c4 = st.columns([3,2,2,1])
    # Local inputs within form
    name = c1.text_input("Meal Name", value=st.session_state.get("meal_name", ""), key="meal_name_form")
    ing = c2.selectbox("Ingredient", options, key="new_ing_form")
    qty = c3.number_input("Qty", min_value=0.0, step=0.1, key="new_qty_form")
    unit = c3.selectbox("Unit", unit_opts0, key="new_unit_form")
    add = c4.form_submit_button("➕ Add Ingredient")
    if add:
        # transfer form state to main session keys
        st.session_state["meal_name"] = name
        st.session_state["new_ing"] = ing
        st.session_state["new_qty"] = qty
        st.session_state["new_unit"] = unit
        add_callback()
        # reset the form for fresh inputs
        st.session_state["new_meal_form_key"] = str(uuid.uuid4())
# Display unsaved ingredients
    if not st.session_state.meal_ingredients.empty:
        st.subheader(f"🧾 Ingredients for '{st.session_state.meal_name}' (unsaved)")
        temp = st.session_state.meal_ingredients.copy()
        temp["Display"] = temp.apply(lambda r: f"{base_to_display(r['Quantity'], base0)[0]:.2f} {r['Input Unit']}", axis=1)
        st.dataframe(temp[["Ingredient","Display","Cost per Unit","Total Cost"]], use_container_width=True)
        if st.button("💾 Save Meal"):
            save_callback()

    # UI: List & Edit Meals
    st.markdown("---")
    st.subheader("📦 Saved Meals")
    if not meals_df.empty:
        for meal in sorted(meals_df['Meal'].unique()):
            cols = st.columns([6,1])
            cols[0].markdown(f"**{meal}**")
            if cols[1].button("✏️", key=f"edit_{meal}"):
                st.session_state.editing_meal = meal
                st.rerun()
    else:
        st.write("No meals saved yet.")

    # Edit existing meal
    if st.session_state.get("editing_meal"):
        mn = st.session_state.editing_meal
        edit_key = f"edit_{mn}_df"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = meals_df[meals_df['Meal']==mn].reset_index(drop=True)
        df_edit = st.session_state[edit_key]
        modal = st.modal(f"Edit Meal: {mn}") if hasattr(st, 'modal') else st.expander(f"Edit Meal: {mn}", expanded=True)
        with modal:
            new_name = st.text_input("Meal Name", value=mn, key=f"rename_{mn}")
            if st.button("🗑️ Delete Meal", key=f"del_{mn}"):
                remaining = meals_df[meals_df['Meal']!=mn]
                remaining.to_csv(MEAL_DATA_PATH, index=False)
                commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Delete meal")
                st.success(f"Deleted {mn}")
                del st.session_state[edit_key]
                del st.session_state['editing_meal']
                st.rerun()

            st.markdown("### Ingredients")
            for idx, r in st.session_state[edit_key].iterrows():
                ing = r['Ingredient']
                base = r['Quantity']
                bu = ingredients_df[ingredients_df['Ingredient']==ing].iloc[0]['Unit Type']
                dq, du = base_to_display(base, bu)
                du = r['Input Unit'] or du
                c1, c2, c3, c4, c5 = st.columns([3,2,2,2,1])
                c1.markdown(f"**{ing}**")
                c2.number_input(f"qty_{mn}_{idx}", value=float(dq), key=f"uq_{mn}_{idx}", label_visibility='collapsed')
                uopts = get_display_unit_options(bu)
                c3.selectbox(f"unit_{mn}_{idx}", uopts, index=uopts.index(du) if du in uopts else 0, key=f"uu_{mn}_{idx}", label_visibility='collapsed')
                if c5.button("Remove", key=f"rm_{mn}_{idx}"):
                    df_tmp = st.session_state[edit_key].drop(idx).reset_index(drop=True)
                    st.session_state[edit_key] = df_tmp
                    st.rerun()

            # Add Ingredient in edit
            st.markdown("#### Add Ingredient")
            a1, a2, a3, a4 = st.columns([3,2,2,1])
            ai_key = f"agi_{mn}"
            aq_key = f"aq_{mn}"
            au_key = f"au_{mn}"
            st.session_state.setdefault(ai_key, options[0] if options else "")
            st.session_state.setdefault(aq_key, 0.0)
            info_e = ingredients_df[ingredients_df['Ingredient']==st.session_state[ai_key]].iloc[0]
            uo_edit = get_display_unit_options(info_e['Unit Type'])
            if au_key not in st.session_state or st.session_state[au_key] not in uo_edit:
                st.session_state[au_key] = uo_edit[0]
            a1.selectbox("", options, key=ai_key, label_visibility='collapsed')
            a2.number_input("", min_value=0.0, step=0.1, key=aq_key, label_visibility='collapsed')
            a3.selectbox("", uo_edit, key=au_key, label_visibility='collapsed')
            if a4.button("➕", key=f"addit_{mn}"):
                qty = st.session_state[aq_key]
                if qty > 0:
                    row = ingredients_df[ingredients_df['Ingredient']==st.session_state[ai_key]].iloc[0]
                    cpu2 = float(row['Cost Per Unit'])
                    bq2 = display_to_base(qty, st.session_state[au_key], row['Unit Type'])
                    tot2 = round(bq2*cpu2,6)
                    entry = {'Ingredient':st.session_state[ai_key],'Quantity':bq2,'Cost per Unit':cpu2,'Total Cost':tot2,'Input Unit':st.session_state[au_key]}
                    st.session_state[edit_key] = pd.concat([st.session_state[edit_key], pd.DataFrame([entry])], ignore_index=True)
                    st.success(f"Added {qty}{st.session_state[au_key]} of {st.session_state[ai_key]}")
                    st.session_state[aq_key] = 0.0
                    st.session_state[au_key] = uo_edit[0]
                    st.rerun()

            # Save Changes
            if st.button("💾 Save Changes", key=f"sv_{mn}"):
                final_name = st.session_state[f"rename_{mn}"].strip() or mn
                df_u = st.session_state[edit_key]
                df_u['Meal'] = final_name
                cols = ['Meal'] + [c for c in df_u.columns if c != 'Meal']
                df_u = df_u[cols]
                others = meals_df[meals_df['Meal'] != mn]
                final_df = pd.concat([others, df_u], ignore_index=True)
                os.makedirs("data", exist_ok=True)
                final_df.to_csv(MEAL_DATA_PATH, index=False)
                commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Save edited meal")
                st.success(f"✅ Changes saved for {final_name}!")
                del st.session_state[edit_key]
                del st.session_state['editing_meal']
                st.rerun() 
