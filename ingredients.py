import streamlit as st
import pandas as pd
import os
import uuid
import base64
import io
import requests
from utils import save_ingredients_to_github

UNIT_TYPE_OPTIONS = ["KG", "L", "Unit"]
DATA_PATH = "data/ingredients.csv"


def load_ingredients():
    if os.path.exists(DATA_PATH):
        return pd.read_csv(DATA_PATH)

    # Load from GitHub fallback
    try:
        token = st.secrets["github_token"]
        repo = st.secrets["github_repo"]
        branch = st.secrets.get("github_branch", "main")
        path = "data/ingredients.csv"

        api_url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(api_url, headers=headers)
        if resp.status_code == 200:
            content = base64.b64decode(resp.json()["content"])
            df = pd.read_csv(io.StringIO(content.decode("utf-8")))

            # Save to local CSV for session persistence
            os.makedirs("data", exist_ok=True)
            df.to_csv(DATA_PATH, index=False)

            return df
    except Exception as e:
        st.warning(f"⚠️ Could not load ingredients from GitHub: {e}")

    return pd.DataFrame(columns=["Ingredient", "Unit Type", "Purchase Size", "Cost"])


def render():
    st.header("📋 Ingredient Manager")
    st.info("Use this tab to manage ingredients used in meals.\n\n**'Purchase Size'** is how much you buy at once (e.g. 5KG).\n**'Unit Type'** specifies if it's in kilograms, litres, or units.\n**'Cost'** is the total cost for the full purchase size.\n\nThe system calculates cost per unit automatically.")

    if "ingredients_df" not in st.session_state:
        st.session_state.ingredients_df = load_ingredients()

    full_df = st.session_state.ingredients_df.copy()

    def live_cost_per_unit(row):
        try:
            return round(float(row["Cost"]) / float(row["Purchase Size"]), 4)
        except (ValueError, ZeroDivisionError, TypeError):
            return None

    saved_df = full_df.dropna(subset=["Ingredient"]).copy()
    saved_df["Cost per Unit"] = saved_df.apply(live_cost_per_unit, axis=1)

    st.subheader("🧾 Saved Ingredients")
    edited_saved_df = st.data_editor(
        saved_df,
        num_rows="dynamic",
        use_container_width=True,
        key="saved_ingredients"
    )

    st.divider()
    st.subheader("➕ New Ingredient Entry")
    if "new_entry_df" not in st.session_state:
        st.session_state.new_entry_df = pd.DataFrame(columns=["Ingredient", "Unit Type", "Purchase Size", "Cost"])

    new_rows = st.session_state.new_entry_df.copy()

    if "ingredient_form_key" not in st.session_state:
        st.session_state.ingredient_form_key = str(uuid.uuid4())

    form_container = st.empty()
    with form_container.form(key=st.session_state.ingredient_form_key):
        cols = st.columns([3, 2, 2, 2])
        with cols[0]:
            name = st.text_input("Ingredient Name", key="ingredient_name")
        with cols[1]:
            unit_type = st.selectbox("Unit Type", UNIT_TYPE_OPTIONS, key="ingredient_unit_type")
        with cols[2]:
            purchase_size = st.number_input("Purchase Size", min_value=0.0, step=0.1, key="ingredient_purchase_size")
        with cols[3]:
            cost = st.number_input("Cost", min_value=0.0, step=0.1, key="ingredient_cost")

        add = st.form_submit_button("➕ Add Ingredient")
        if add and name and purchase_size:
            new_rows.loc[len(new_rows)] = {
                "Ingredient": name,
                "Unit Type": unit_type,
                "Purchase Size": purchase_size,
                "Cost": cost
            }
            st.session_state.new_entry_df = new_rows
            for key in ["ingredient_name", "ingredient_unit_type", "ingredient_purchase_size", "ingredient_cost"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.ingredient_form_key = str(uuid.uuid4())
            st.rerun()

    if not new_rows.empty:
        new_rows["Cost per Unit"] = new_rows.apply(live_cost_per_unit, axis=1)
        st.dataframe(new_rows, use_container_width=True)

    if st.button("💾 Save Ingredients"):
        with st.spinner("Saving ingredients..."):
            combined = pd.concat([edited_saved_df, new_rows], ignore_index=True)
            combined["Cost per Unit"] = combined.apply(live_cost_per_unit, axis=1)
            st.session_state.ingredients_df = combined

            save_ingredients_to_github(combined)

            st.success("✅ Ingredients saved!")
            st.session_state.new_entry_df = pd.DataFrame(columns=["Ingredient", "Unit Type", "Purchase Size", "Cost"])
            st.session_state.ingredient_form_key = str(uuid.uuid4())
            st.rerun()
