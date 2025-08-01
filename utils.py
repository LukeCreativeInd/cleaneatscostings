import os
import pandas as pd
import base64
import requests
import streamlit as st

def save_ingredients_to_github(df: pd.DataFrame):
    # Required secrets: github_token, github_repo, github_branch
    token = st.secrets["github_token"]
    repo = st.secrets["github_repo"]  # e.g. 'username/repo'
    branch = st.secrets.get("github_branch", "main")
    path = "data/ingredients.csv"

    # Save CSV locally (optional)
    os.makedirs("data", exist_ok=True)
    df.to_csv(path, index=False)

    # Prepare API request to GitHub
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"

    # Get the current SHA of the file (required for updating)
    headers = {"Authorization": f"Bearer {token}"}
    sha = None
    resp = requests.get(api_url, headers=headers)
    if resp.status_code == 200:
        sha = resp.json()["sha"]

    # Read and encode file content
    with open(path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    # Prepare commit payload
    payload = {
        "message": "Update ingredients.csv from Streamlit",
        "content": content,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    # Send PUT request
    put_resp = requests.put(api_url, headers=headers, json=payload)
    if put_resp.status_code not in [200, 201]:
        st.error(f"❌ GitHub push failed: {put_resp.status_code} - {put_resp.text}")
        raise RuntimeError("GitHub push failed")
