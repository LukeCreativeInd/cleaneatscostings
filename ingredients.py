import streamlit as st
import pandas as pd
import os
import requests
import base64
import io

# ----------------------
# Config
# ----------------------
DATA_PATH   = "data/ingredients.csv"
GITHUB_PATH = "data/ingredients.csv"

# ----------------------
# Data handling
# ----------------------
def load_ingredients():
    """
    Load ingredients from GitHub if configured, else fallback to local file.
    """
    token = st.secrets.get("github_token")
    repo  = st.secrets.get("github_repo")
    branch= st.secrets.get("github_branch", "main")

    # Try GitHub
    if token and repo:
        try:
            api_url = f"https://api.github.com/repos/{repo}/contents/{GITHUB_PATH}?ref={branch}"
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.get(api_url, headers=headers)
            if resp.status_code == 200:
                content = base64.b64decode(resp.json()["content"])
                df = pd.read_csv(io.StringIO(content.decode("utf-8")))
                df.columns = df.columns.str.strip().str.title()
                # Standardize
                df["Ingredient"]   = df["Ingredient"].astype(str).str.strip().str.title()
                df["Unit Type"]    = df.get("Unit Type", "Unit").astype(str).str.strip().str.upper()
                df["Purchase Size"]= pd.to_numeric(df.get("Purchase Size", 0), errors="coerce").fillna(0)
                df["Cost"]         = pd.to_numeric(df.get("Cost", 0), errors="coerce").fillna(0)
                df["Cost Per Unit"]= df["Cost"] / df["Purchase Size"].replace(0, 1)
                # Cache locally
                os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
                df.to_csv(DATA_PATH, index=False)
                return df
            else:
                st.warning(f"❌ GitHub API error {resp.status_code}")
        except Exception as e:
            st.warning(f"⚠️ Exception loading from GitHub: {e}")

    # Fallback
    if os.path.exists(DATA_PATH):
        return pd.read_csv(DATA_PATH)
    return pd.DataFrame(columns=["Ingredient", "Unit Type", "Purchase Size", "Cost", "Cost Per Unit"])


def save_ingredients(df: pd.DataFrame):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    df.to_csv(DATA_PATH, index=False)
    # Try commit
    try:
        from meal_builder import commit_file_to_github
        commit_file_to_github(DATA_PATH, GITHUB_PATH, "Update ingredients.csv")
    except Exception as e:
        st.warning(f"⚠️ GitHub commit failed: {e}")


# Callback to save & stay on this tab
def _save_and_stay(edited_df):
    save_ingredients(edited_df)
    st.success("Ingredients updated successfully.")
    st.rerun()


# ----------------------
# Main render
# ----------------------
def render():
    st.header("📋 Ingredients")
    st.info("Use this tab to manage ingredients used in meals.")

    # New Ingredient Form
    st.subheader("New Ingredient Entry")
    with st.form("add_ing_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        name = c1.text_input("Ingredient Name")
        unit = c2.selectbox("Unit Type", ["KG", "L", "Unit"])
        size = c3.number_input("Purchase Size", min_value=0.0, step=0.1)
        cost = c4.number_input("Cost", min_value=0.0, step=0.01)
        submitted = st.form_submit_button("➕ Add Ingredient")
        if submitted:
            if not name.strip():
                st.warning("Ingredient Name cannot be blank.")
            else:
                df_all = load_ingredients()
                new_row = {
                    "Ingredient":    name.strip().title(),
                    "Unit Type":     unit,
                    "Purchase Size": size,
                    "Cost":          cost,
                    "Cost Per Unit": cost / size if size else 0,
                }
                df_all = pd.concat([df_all, pd.DataFrame([new_row])], ignore_index=True)
                save_ingredients(df_all)
                st.success(f"Added '{name.strip()}' successfully.")
                st.rerun()

    # Existing Ingredients
    df = load_ingredients()
    st.subheader("Saved Ingredients")
    if df.empty:
        st.write("No saved ingredients yet.")
    else:
        edited = st.data_editor(df, num_rows="dynamic")
        # use on_click callback so we call st.rerun() *after* saving
        if st.button("💾 Save Ingredients", key="save_ings", on_click=_save_and_stay, args=(edited,)):
            # the callback will handle save + rerun
            pass
