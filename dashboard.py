import streamlit as st
import pandas as pd
import os
import requests
import base64
from datetime import datetime

MEALS_PATH = "data/meals.csv"
SUMMARY_PATH = "data/stored_total_summary.csv"

# ----------------------
# Load & Save Helpers
# ----------------------
def load_stored_summary():
    if os.path.exists(SUMMARY_PATH):
        df = pd.read_csv(SUMMARY_PATH)
        df.columns = df.columns.str.strip().str.title()
        return df
    cols = ["Meal", "Other Costs", "Sell Price"]
    return pd.DataFrame(columns=cols)


def save_summary_to_github(df: pd.DataFrame):
    os.makedirs(os.path.dirname(SUMMARY_PATH), exist_ok=True)
    df.to_csv(SUMMARY_PATH, index=False)
    try:
        token = st.secrets["github_token"]
        repo = st.secrets["github_repo"]
        branch = st.secrets.get("github_branch", "main")
    except KeyError:
        st.warning("Missing GitHub secrets; saved locally only.")
        return
    api_url = f"https://api.github.com/repos/{repo}/contents/{SUMMARY_PATH}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    # get existing sha
    resp = requests.get(api_url, headers=headers, params={"ref": branch})
    sha = resp.json().get("sha") if resp.status_code == 200 else None
    content = base64.b64encode(df.to_csv(index=False).encode()).decode()
    payload = {
        "message": f"Update costing summary {datetime.utcnow().isoformat()}Z",
        "content": content,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    put = requests.put(api_url, headers=headers, json=payload)
    if put.status_code not in (200, 201):
        st.error(f"GitHub commit failed: {put.status_code}")

# ----------------------
# Main render
# ----------------------
def render():
    st.header("💰 Costing Dashboard")
    st.markdown("Edit **Other Costs** and **Sell Price** below; totals update automatically.")

    # Load data
    if os.path.exists(MEALS_PATH):
        meals_df = pd.read_csv(MEALS_PATH)
    else:
        st.warning("No meals.csv found; build meals first.")
        return

    base = meals_df.groupby("Meal")["Total Cost"].sum().reset_index().rename(columns={"Total Cost": "Ingredients"})
    stored = load_stored_summary()
    merged = base.merge(stored, on="Meal", how="left")
    merged["Other Costs"] = merged["Other Costs"].fillna(0.0)
    merged["Sell Price"] = merged["Sell Price"].fillna(merged["Ingredients"] + merged["Other Costs"])
    merged["Total Cost"] = merged["Ingredients"] + merged["Other Costs"]
    merged["Profit Margin"] = merged["Sell Price"] - merged["Total Cost"]
    merged["Margin %"] = merged.apply(lambda r: (r["Profit Margin"]/r["Sell Price"]*100) if r["Sell Price"] else 0.0, axis=1)

    # Editable editor
    st.subheader("📦 Per-Meal Cost Summary")
    editable = merged[["Meal", "Ingredients", "Other Costs", "Sell Price"]].copy()
    edited = st.data_editor(
        editable,
        key="costing_editor",
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Meal": st.column_config.TextColumn("Meal", disabled=True),
            "Ingredients": st.column_config.NumberColumn("Ingredients", format="${:.2f}", disabled=True),
            "Other Costs": st.column_config.NumberColumn("Other Costs", format="${:.2f}"),
            "Sell Price": st.column_config.NumberColumn("Sell Price", format="${:.2f}"),
        },
    )
    # Recompute fields
    edited["Total Cost"] = edited["Ingredients"] + edited["Other Costs"]
    edited["Profit Margin"] = edited["Sell Price"] - edited["Total Cost"]
    edited["Margin %"] = edited.apply(lambda r: (r["Profit Margin"]/r["Sell Price"]*100) if r["Sell Price"] else 0.0, axis=1)

    # Final table
    st.subheader("🔍 Finalized Summary")
    st.dataframe(
        edited.style.format({
            "Ingredients": "${:.2f}",
            "Other Costs": "${:.2f}",
            "Total Cost": "${:.2f}",
            "Sell Price": "${:.2f}",
            "Profit Margin": "${:.2f}",
            "Margin %": "{:.1f}%",
        }),
        use_container_width=True,
    )

    # Aggregate metrics
    total_ing = edited["Ingredients"].sum()
    total_other = edited["Other Costs"].sum()
    total_cost = edited["Total Cost"].sum()
    total_sell = edited["Sell Price"].sum()
    total_profit = edited["Profit Margin"].sum()
    overall = (total_profit/total_sell*100) if total_sell else 0.0
    cols = st.columns(6)
    cols[0].metric("Total Ingredient Cost", f"${total_ing:,.2f}")
    cols[1].metric("Total Other Costs", f"${total_other:,.2f}")
    cols[2].metric("Total Cost", f"${total_cost:,.2f}")
    cols[3].metric("Total Sell Price", f"${total_sell:,.2f}")
    cols[4].metric("Total Profit", f"${total_profit:,.2f}")
    cols[5].metric("Overall Margin %", f"{overall:.1f}%")

    # Save button
    if st.button("💾 Save Costing Summary", key="save_summary"):
        final_df = edited[["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"]].copy()
        from app import save_data
        save_data(final_df)
        save_summary_to_github(final_df)
        st.success("✅ Costing summary saved and committed.")
