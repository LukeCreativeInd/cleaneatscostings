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
    # ensure columns exist
    return pd.DataFrame(columns=["Meal", "Other Costs", "Sell Price"])


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
    url = f"https://api.github.com/repos/{repo}/contents/{SUMMARY_PATH}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    resp = requests.get(url, headers=headers, params={"ref": branch})
    sha = resp.json().get("sha") if resp.status_code == 200 else None
    content = base64.b64encode(df.to_csv(index=False).encode()).decode()
    payload = {"message": f"Update costing summary {datetime.utcnow().isoformat()}Z", "content": content, "branch": branch}
    if sha:
        payload["sha"] = sha
    put = requests.put(url, headers=headers, json=payload)
    if put.status_code not in (200, 201):
        st.error(f"GitHub commit failed: {put.status_code} {put.text}")

# ----------------------
# Main render
# ----------------------
def render():
    st.header("💰 Costing Dashboard")
    st.markdown("Edit **Other Costs** and **Sell Price** below; totals recalc automatically.")

    if not os.path.exists(MEALS_PATH):
        st.warning("No meals data found. Create meals first in the Meals tab.")
        return

    meals_df = pd.read_csv(MEALS_PATH)
    if meals_df.empty:
        st.warning("No meals in meals.csv. Build a meal first.")
        return

    # Aggregate base ingredient costs
    cost_df = (
        meals_df.groupby("Meal", as_index=False)
        .agg(Ingredients=("Total Cost", "sum"))
    )

    # Load stored overrides
    stored = load_stored_summary()

    # Merge and fill defaults    summary = pd.merge(cost_df, stored, on="Meal", how="left")
    # Ensure 'Other Costs' exists and fill nulls
    if "Other Costs" not in summary.columns:
        summary["Other Costs"] = 0.0
    else:
        summary["Other Costs"] = summary["Other Costs"].fillna(0.0)
    # Ensure 'Sell Price' exists and fill nulls from ingredients + other costs
    if "Sell Price" not in summary.columns:
        summary["Sell Price"] = summary["Ingredients"] + summary["Other Costs"]
    else:
        summary["Sell Price"] = summary["Sell Price"].fillna(
            summary["Ingredients"] + summary["Other Costs"]
        )

    # Compute derived metrics
    summary["Total Cost"] = summary["Ingredients"] + summary["Other Costs"]
    summary["Profit Margin"] = summary["Sell Price"] - summary["Total Cost"]
    summary["Margin %"] = summary.apply(
        lambda r: (r["Profit Margin"] / r["Sell Price"] * 100)
        if r["Sell Price"] else 0.0,
        axis=1,
    )

    # Editable per-meal summary
    st.subheader("📦 Per-Meal Cost Summary")
    editor = st.data_editor(
        summary[["Meal", "Ingredients", "Other Costs", "Sell Price"]],
        key="cost_editor_v2",
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Meal": st.column_config.TextColumn(disabled=True),
            "Ingredients": st.column_config.NumberColumn(prefix="$", format=",.2f", disabled=True),
            "Other Costs": st.column_config.NumberColumn(prefix="$", format=",.2f"),
            "Sell Price": st.column_config.NumberColumn(prefix="$", format=",.2f"),
        },
    )

    # Recompute and display finalized table
    final = editor.copy()
    final["Total Cost"] = final["Ingredients"] + final["Other Costs"]
    final["Profit Margin"] = final["Sell Price"] - final["Total Cost"]
    final["Margin %"] = final.apply(
        lambda r: (r["Profit Margin"] / r["Sell Price"] * 100) if r["Sell Price"] else 0.0,
        axis=1,
    )

    st.subheader("🔍 Finalized Summary")
    st.dataframe(
        final.style.format({
            "Ingredients": "${:,.2f}",
            "Other Costs": "${:,.2f}",
            "Total Cost": "${:,.2f}",
            "Sell Price": "${:,.2f}",
            "Profit Margin": "${:,.2f}",
            "Margin %": "{:.1f}%",
        }),
        use_container_width=True,
    )

    # Aggregate metrics
    total_ing = final["Ingredients"].sum()
    total_other = final["Other Costs"].sum()
    total_cost = final["Total Cost"].sum()
    total_sell = final["Sell Price"].sum()
    total_profit = final["Profit Margin"].sum()
    overall = (total_profit / total_sell * 100) if total_sell else 0.0
    mcols = st.columns(6)
    mcols[0].metric("Total Ingredient Cost", f"${total_ing:,.2f}")
    mcols[1].metric("Total Other Costs", f"${total_other:,.2f}")
    mcols[2].metric("Total Cost", f"${total_cost:,.2f}")
    mcols[3].metric("Total Sell Price", f"${total_sell:,.2f}")
    mcols[4].metric("Total Profit", f"${total_profit:,.2f}")
    mcols[5].metric("Overall Margin %", f"{overall:.1f}%")

    # Save button
    if st.button("💾 Save Costing Summary", key="save_summary_v2"):
        to_save = final[["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"]]
        save_summary_to_github(to_save)
        st.success("✅ Costing summary saved and committed.")
