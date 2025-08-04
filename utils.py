import streamlit as st
import os
import pandas as pd
import base64
import requests
from datetime import datetime

def save_ingredients_to_github(df: pd.DataFrame):
    os.makedirs("data", exist_ok=True)
    df.to_csv("data/ingredients.csv", index=False)

    token = st.secrets["github_token"]
    repo = st.secrets["github_repo"]
    branch = st.secrets.get("github_branch", "main")
    path = "data/ingredients.csv"

    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    get_resp = requests.get(api_url, headers=headers, params={"ref": branch})
    if get_resp.status_code == 200:
        sha = get_resp.json()["sha"]
    else:
        sha = None

    content = base64.b64encode(df.to_csv(index=False).encode()).decode()
    data = {
        "message": f"Update ingredients at {datetime.utcnow().isoformat()}Z",
        "content": content,
        "branch": branch
    }
    if sha:
        data["sha"] = sha

    put_resp = requests.put(api_url, headers=headers, json=data)
    if put_resp.status_code not in [200, 201]:
        raise RuntimeError(f"GitHub API error: {put_resp.status_code}, {put_resp.text}")

def save_business_costs_to_github(df: pd.DataFrame):
    os.makedirs("data", exist_ok=True)
    df.to_csv("data/business_costs.csv", index=False)

    token = st.secrets["github_token"]
    repo = st.secrets["github_repo"]
    branch = st.secrets.get("github_branch", "main")
    path = "data/business_costs.csv"

    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    get_resp = requests.get(api_url, headers=headers, params={"ref": branch})
    if get_resp.status_code == 200:
        sha = get_resp.json()["sha"]
    else:
        sha = None

    content = base64.b64encode(df.to_csv(index=False).encode()).decode()
    data = {
        "message": f"Update business costs at {datetime.utcnow().isoformat()}Z",
        "content": content,
        "branch": branch
    }
    if sha:
        data["sha"] = sha

    put_resp = requests.put(api_url, headers=headers, json=data)
    if put_resp.status_code not in [200, 201]:
        raise RuntimeError(f"GitHub API error: {put_resp.status_code}, {put_resp.text}")
