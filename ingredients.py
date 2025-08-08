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
    token  = st.secrets.get("github_token")
    repo   = st.secrets.get("github_repo")
    branch = st.secrets.get("github_branch", "main")

    if token and repo:
        try:
            api_url = f"https://api.github.com/repos/{repo}/contents/{GITHUB_PATH}?ref={branch}"
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.get(api_url, headers=headers)
            if resp.status_code == 200:
                content = base64.b64decode(resp.json()["content"])
                df = pd.read_csv(io.StringIO(content.decode("utf-8")))
                df.columns = df.columns.str.strip().str.title()
                df["Ingredient"]   = df["Ingredient"].astype(str).str.strip().str.title()
                df["Unit Type"]    = df.get("Unit Type","Unit").astype(str).str.strip().str.upper()
                df["Purchase Size"]= pd.to_numeric(df.get("Purchase Size",0), errors="coerce").fillna(0)
                df["Cost"]         = pd.to_numeric(df.get("Cost",0), errors="coerce").fillna(0)
                df["Cost Per Unit"]= df["Cost"] / df["Purchase Size"].replace(0,1)
                os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
                df.to_csv(DATA_PATH, index=False)
                return df
            else:
                st.warning(f"❌ GitHub API error {resp.status_code}")
        except Exception as e:
            st.warning(f"⚠️ Exception loading from GitHub: {e}")

    # fallback
    if os.path.exists(DATA_PATH):
        return pd.read_csv(DATA_PATH)
    return pd.DataFrame(columns=[
        "Ingredient","Unit Type","Purchase Size","Cost","Cost Per Unit"
    ])


def commit_file_to_github(local_path, repo_path, msg):
    try:
        token  = st.secrets["github_token"]
        repo   = st.secrets["github_repo"]
        branch = st.secrets.get("github_branch","main")
    except:
        return
    url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json"}
    with open(local_path,"rb") as f:
        content = base64.b64encode(f.read()).decode()
    resp = requests.get(url, headers=headers, params={"ref":branch})
    sha  = resp.json().get("sha") if resp.status_code==200 else None
    payload={"message":f"{msg} {pd.Timestamp.utcnow().isoformat()}Z",
             "content":content,"branch":branch}
    if sha:
        payload["sha"] = sha
    put = requests.put(url, headers=headers, json=payload)
    if put.status_code not in (200,201):
        st.warning(f"⚠️ GitHub commit failed: {put.status_code}")


def save_ingredients_to_disk():
    """Called by bottom ‘Save Ingredients’ button."""
    df_existing = load_ingredients()
    df_new      = st.session_state["new_ings"]
    out = pd.concat([df_existing, df_new], ignore_index=True)
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    out.to_csv(DATA_PATH, index=False)
    commit_file_to_github(DATA_PATH, GITHUB_PATH, "Update ingredients.csv")
    st.success(f"✅ Saved {len(df_new)} ingredient(s).")
    st.session_state["new_ings"] = pd.DataFrame(columns=df_new.columns)


# ----------------------
# Main render
# ----------------------
def render():
    st.header("📋 Ingredients")
    st.info("Use this tab to manage ingredients used in meals.")

    df = load_ingredients()

    # initialize a buffer in session_state
    st.session_state.setdefault("new_ings", pd.DataFrame(
        columns=["Ingredient","Unit Type","Purchase Size","Cost","Cost Per Unit"]
    ))

    with st.form("new_ing_form", clear_on_submit=True):
        c1,c2,c3,c4 = st.columns([3,1,1,1])
        name = c1.text_input("Ingredient Name")
        unit = c2.selectbox("Unit Type", ["KG","L","UNIT"])
        size = c3.number_input("Purchase Size", value=0.0, min_value=0.0, step=0.1)
        cost = c4.number_input("Cost", value=0.0, min_value=0.0, step=0.01)

        submitted = st.form_submit_button("➕ Add Ingredient")
        if submitted:
            cpu = (cost / size) if size else 0.0
            new_row = {
                "Ingredient":     name.strip().title(),
                "Unit Type":      unit,
                "Purchase Size":  size,
                "Cost":           cost,
                "Cost Per Unit":  cpu
            }
            st.session_state["new_ings"] = pd.concat([
                st.session_state["new_ings"],
                pd.DataFrame([new_row])
            ], ignore_index=True)
            st.success(f"Added '{name.strip().title()}' to draft list.")

    if not st.session_state["new_ings"].empty:
        st.subheader("📝 Pending Ingredients (draft)")
        st.table(st.session_state["new_ings"])

    st.subheader("📦 Saved Ingredients")
    st.dataframe(df)

    if not st.session_state["new_ings"].empty:
        st.button("💾 Save Ingredients", on_click=save_ingredients_to_disk)
