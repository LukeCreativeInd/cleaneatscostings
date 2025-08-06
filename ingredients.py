import streamlit as st
import pandas as pd
import os
import requests
import base64
import io

# ----------------------
# Config
# ----------------------
DATA_PATH = "data/ingredients.csv"
GITHUB_PATH = "data/ingredients.csv"

# ----------------------
# Data handling
# ----------------------
def load_ingredients():
    """
    Load ingredients from GitHub if configured, else fallback to local file.
    """
    # If GitHub secrets missing, load from local CSV directly
    token = st.secrets.get("github_token")
    repo = st.secrets.get("github_repo")
    if not token or not repo:
        if os.path.exists(DATA_PATH):
            return pd.read_csv(DATA_PATH)
        return pd.DataFrame(columns=["Ingredient", "Unit Type", "Purchase Size", "Cost", "Cost Per Unit"])
    
    # Attempt GitHub fetch
    try:
        branch = st.secrets.get("github_branch", "main")
        api_url = f"https://api.github.com/repos/{repo}/contents/{GITHUB_PATH}?ref={branch}"
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(api_url, headers=headers)
        if resp.status_code == 200:
            content = base64.b64decode(resp.json()["content"])
            df = pd.read_csv(io.StringIO(content.decode("utf-8")))
            df.columns = df.columns.str.strip().str.title()
            # Standardize
            df["Ingredient"] = df["Ingredient"].astype(str).str.strip().str.title()
            df["Unit Type"] = df.get("Unit Type", "unit").astype(str).str.strip().str.upper()
            df["Purchase Size"] = pd.to_numeric(df.get("Purchase Size", 0), errors="coerce").fillna(0)
            df["Cost"] = pd.to_numeric(df.get("Cost", 0), errors="coerce").fillna(0)
            df["Cost Per Unit"] = df["Cost"] / df["Purchase Size"].replace(0, 1)
            # Save local copy
            os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
            df.to_csv(DATA_PATH, index=False)
            return df
        else:
            st.warning(f"❌ GitHub API error {resp.status_code}: {resp.text}")
    except Exception as e:
        st.warning(f"⚠️ Exception loading ingredients: {e}")

    # Final fallback to local file
    if os.path.exists(DATA_PATH):
        return pd.read_csv(DATA_PATH)
    return pd.DataFrame(columns=["Ingredient", "Unit Type", "Purchase Size", "Cost", "Cost Per Unit"])

# ----------------------
# Main render
# ----------------------

def render():
    st.header("📋 Ingredients")
    st.info("Use this tab to manage ingredients used in meals.")

    df = load_ingredients()

    # Display existing
    st.subheader("Saved Ingredients")
    if df.empty:
        st.write("No saved ingredients yet.")
    else:
        edited = st.data_editor(df, num_rows="dynamic")
        if st.button("💾 Save Ingredients"):
            os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
            edited.to_csv(DATA_PATH, index=False)
            st.success("Ingredients updated successfully.")

    # Add new
    st.subheader("New Ingredient Entry")
    with st.form("add_ing_form"):
        c1, c2, c3, c4 = st.columns(4)
        name = c1.text_input("Ingredient Name")
        unit = c2.selectbox("Unit Type", ["KG","L","Unit"])
        size = c3.number_input("Purchase Size", min_value=0.0, step=0.1)
        cost = c4.number_input("Cost", min_value=0.0, step=0.01)
        submitted = st.form_submit_button("➕ Add Ingredient")
        if submitted:
            if not name.strip():
                st.warning("Ingredient Name cannot be blank.")
            else:
                new = {
                    "Ingredient": name.strip().title(),
                    "Unit Type": unit,
                    "Purchase Size": size,
                    "Cost": cost,
                    "Cost Per Unit": cost / size if size else 0,
                }
                df2 = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
                df2.to_csv(DATA_PATH, index=False)
                st.success(f"Added '{name.strip()}' successfully.")
                st.rerun()
