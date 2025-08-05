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

    # Load data
    meals_df = load_meals()
    ingredients_df = load_ingredients()
    options = sorted(ingredients_df["Ingredient"].unique())

    # Session defaults
    st.session_state.setdefault("meal_name", "")
    st.session_state.setdefault("meal_ingredients", pd.DataFrame(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"]))

    # Callbacks modify session state then rerun
    def add_callback():
        name = st.session_state["meal_name"]
        qty = st.session_state["new_qty"]
        row = ingredients_df[ingredients_df["Ingredient"] == st.session_state["new_ing"]].iloc[0]
        cpu = float(row["Cost Per Unit"])
        bq = display_to_base(qty, st.session_state["new_unit"], row["Unit Type"])
        total = round(bq * cpu, 6)
        entry = {"Ingredient":row["Ingredient"],"Quantity":bq,"Cost per Unit":cpu,"Total Cost":total,"Input Unit":st.session_state["new_unit"]}
        st.session_state["meal_ingredients"] = pd.concat([st.session_state["meal_ingredients"], pd.DataFrame([entry])], ignore_index=True)
        st.success(f"Added {qty}{st.session_state['new_unit']} of {row['Ingredient']}")
        st.rerun()

    def save_callback():
        combined = pd.concat([meals_df, st.session_state["meal_ingredients"].assign(Meal=st.session_state["meal_name"])], ignore_index=True)
        os.makedirs("data", exist_ok=True)
        combined.to_csv(MEAL_DATA_PATH, index=False)
        commit_file_to_github(MEAL_DATA_PATH, "data/meals.csv", "Update meals")
        st.success("✅ Meal saved!")
        # Reset unsaved ingredients and regenerate form
        st.session_state["meal_ingredients"] = pd.DataFrame(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"])
        st.session_state["meal_form_key"] = str(uuid.uuid4())
        # Trigger rerun to clear form
        st.rerun()(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"])
        st.rerun()

    # Initialize form key for Create/Add Meal
    st.session_state.setdefault("meal_form_key", str(uuid.uuid4()))
    form_key = st.session_state["meal_form_key"]
    # Create/Add Meal form
    with st.form(key=form_key):
        st.subheader("Create / Add Meal")
        c1, c2, c3, c4 = st.columns([3,2,2,1])
        c1.text_input("Meal Name", key="meal_name")
        c2.selectbox("Ingredient", options, key="new_ing")
        c3.number_input("Qty", min_value=0.0, step=0.1, key="new_qty")
        # Determine unit options per ingredient
        row = ingredients_df[ingredients_df["Ingredient"] == st.session_state["new_ing"]].iloc[0]
        unit_opts = get_display_unit_options(row["Unit Type"])
        c3.selectbox("Unit", unit_opts, key="new_unit")
        add = c4.form_submit_button("➕ Add Ingredient")
        if add:
            if not st.session_state["meal_name"]:
                st.warning("Enter meal name first.")
            elif st.session_state["new_qty"] <= 0:
                st.warning("Quantity must be >0.")
            else:
                add_callback()
            # regenerate form key to reset fields
            st.session_state["meal_form_key"] = str(uuid.uuid4())
    
    # Show unsaved ingredients & Save
    if not st.session_state["meal_ingredients"].empty:
        st.subheader(f"🧾 Ingredients for '{st.session_state['meal_name']}' (unsaved)")
        df_temp = st.session_state["meal_ingredients"].copy()
        df_temp["Display"] = df_temp.apply(lambda r: f"{base_to_display(r['Quantity'], r['Input Unit'])[0]:.2f} {r['Input Unit']}", axis=1)
        st.dataframe(df_temp[["Ingredient","Display","Cost per Unit","Total Cost"]], use_container_width=True)
        if st.button("💾 Save Meal"):
            save_callback()

    # Edit saved meals
    st.markdown("---")
    st.subheader("📦 Saved Meals")
    if meals_df.empty:
        st.write("No meals saved yet.")
    else:
        for meal in sorted(meals_df['Meal'].unique()):
            cols = st.columns([6,1])
            cols[0].markdown(f"**{meal}**")
            if cols[1].button("✏️", key=f"edit_{meal}"):
                st.session_state["editing_meal"] = meal
                st.rerun()

    # Edit modal
    if st.session_state.get("editing_meal"):
        mn = st.session_state["editing_meal"]
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
                del st.session_state["editing_meal"]
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
            ai = a1.selectbox("", options, key=f"agi_{mn}", label_visibility='collapsed')
            info_e = ingredients_df[ingredients_df['Ingredient']==ai].iloc[0]
            bu_e = info_e['Unit Type']
            aq = a2.number_input("", min_value=0.0, step=0.1, key=f"aq_{mn}", label_visibility='collapsed')
            au_opts = get_display_unit_options(bu_e)
            au = a3.selectbox("", au_opts, key=f"au_{mn}", label_visibility='collapsed')
            if a4.button("➕", key=f"addit_{mn}") and aq>0:
                cpu2 = float(info_e['Cost Per Unit'])
                bq2 = display_to_base(aq, au, bu_e)
                tot2 = round(bq2*cpu2,6)
                entry = {'Ingredient':ai,'Quantity':bq2,'Cost per Unit':cpu2,'Total Cost':tot2,'Input Unit':au}
                st.session_state[edit_key] = pd.concat([st.session_state[edit_key], pd.DataFrame([entry])], ignore_index=True)
                st.success(f"Added {aq}{au} of {ai}")
                st.rerun()

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
                del st.session_state["editing_meal"]
                st.rerun()
