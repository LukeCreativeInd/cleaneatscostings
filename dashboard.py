import streamlit as st
import pandas as pd
import os
import base64
import requests
from datetime import datetime

MEALS_PATH = "data/meals.csv"
SUMMARY_PATH = "data/stored_total_summary.csv"

# ----------------------
# Load & commit helpers
# ----------------------
def load_stored_summary():
    if os.path.exists(SUMMARY_PATH):
        df = pd.read_csv(SUMMARY_PATH)
        df.columns = df.columns.str.strip().str.title()
        return df
    return pd.DataFrame(columns=["Meal", "Other Costs", "Sell Price"])


def save_summary_to_github(df: pd.DataFrame):
    # Write locally
    os.makedirs(os.path.dirname(SUMMARY_PATH), exist_ok=True)
    df.to_csv(SUMMARY_PATH, index=False)
    # Commit to GitHub
    try:
        token = st.secrets["github_token"]
        repo = st.secrets["github_repo"]
        branch = st.secrets.get("github_branch", "main")
    except KeyError:
        st.warning("Missing GitHub secrets; saved locally only.")
        return
    api_url = f"https://api.github.com/repos/{repo}/contents/{SUMMARY_PATH}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
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
        st.error(f"GitHub commit failed: {put.status_code} {put.text}")

# ----------------------
# Main render
# ----------------------
def render():
    st.header("💰 Costing Dashboard")
    st.markdown("Edit **Other Costs** and **Sell Price** below; totals recalculated automatically.")

    if not os.path.exists(MEALS_PATH):
        st.warning("No meals data found. Create meals first.")
        return

    meals_df = pd.read_csv(MEALS_PATH)
    if meals_df.empty:
        st.warning("No meals in meals.csv. Build a meal first.")
        return

    # Aggregate base costs
    base = (
        meals_df.groupby("Meal")["Total Cost"]
        .sum()
        .reset_index()
        .rename(columns={"Total Cost": "Ingredients"})
    )

    stored = load_stored_summary()
    merged = base.merge(stored, on="Meal", how="left")
    merged["Other Costs"] = merged["Other Costs"].fillna(0.0)
    merged["Sell Price"] = merged["Sell Price"].fillna(
        merged["Ingredients"] + merged["Other Costs"]
    )
    merged["Total Cost"] = merged["Ingredients"] + merged["Other Costs"]
    merged["Profit Margin"] = merged["Sell Price"] - merged["Total Cost"]
    merged["Margin %"] = merged.apply(
        lambda r: (r["Profit Margin"] / r["Sell Price"] * 100) if r["Sell Price"] else 0.0,
        axis=1,
    )

    # Editable summary
    st.subheader("📦 Per-Meal Cost Summary")
    editor = st.data_editor(
        merged[["Meal", "Ingredients", "Other Costs", "Sell Price"]],
        key="costing_editor",
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Meal": st.column_config.TextColumn(disabled=True),
            "Ingredients": st.column_config.NumberColumn(format="$,.2f", disabled=True),
            "Other Costs": st.column_config.NumberColumn(format="$,.2f"),
            "Sell Price": st.column_config.NumberColumn(format="$,.2f"),
        },
    )

    # Recompute derived fields
    editor["Total Cost"] = editor["Ingredients"] + editor["Other Costs"]
    editor["Profit Margin"] = editor["Sell Price"] - editor["Total Cost"]
    editor["Margin %"] = editor.apply(
        lambda r: (r["Profit Margin"] / r["Sell Price"] * 100) if r["Sell Price"] else 0.0,
        axis=1,
    )

    # Finalized summary
    st.subheader("🔍 Finalized Summary")
    st.dataframe(
        editor.style.format({
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
    total_ing = editor["Ingredients"].sum()
    total_other = editor["Other Costs"].sum()
    total_cost = editor["Total Cost"].sum()
    total_sell = editor["Sell Price"].sum()
    total_profit = editor["Profit Margin"].sum()
    overall = (total_profit / total_sell * 100) if total_sell else 0.0
    cols = st.columns(6)
    cols[0].metric("Total Ingredient Cost", f"${total_ing:,.2f}")
    cols[1].metric("Total Other Costs", f"${total_other:,.2f}")
    cols[2].metric("Total Cost", f"${total_cost:,.2f}")
    cols[3].metric("Total Sell Price", f"${total_sell:,.2f}")
    cols[4].metric("Total Profit", f"${total_profit:,.2f}")
    cols[5].metric("Overall Margin %", f"{overall:.1f}%")

    # Save button without re-import
    if st.button("💾 Save Costing Summary", key="save_summary_button"):
        final_df = editor[["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"]]
        save_summary_to_github(final_df)
        st.success("✅ Costing summary saved and committed.")
