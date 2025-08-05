import streamlit as st
import pandas as pd
import os
import base64
import requests
from datetime import datetime

MEALS_PATH = "data/meals.csv"
SUMMARY_PATH = "data/stored_total_summary.csv"

# ----------------------
# Helpers
# ----------------------
def load_stored_summary():
    if os.path.exists(SUMMARY_PATH):
        df = pd.read_csv(SUMMARY_PATH)
        df.columns = df.columns.str.strip().str.title()
        return df
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
    st.markdown("Edit **Other Costs** and **Sell Price** below; totals recalc automatically.")

    if not os.path.exists(MEALS_PATH):
        st.warning("No meals data found. Create meals first.")
        return

    meals_df = pd.read_csv(MEALS_PATH)
    if meals_df.empty:
        st.warning("No meals saved. Build a meal first.")
        return

    # Aggregate base costs per meal
    base = (
        meals_df.groupby("Meal", as_index=False)["Total Cost"]
        .sum()
        .rename(columns={"Total Cost": "Ingredients"})
    )

    # Load overrides
    stored = load_stored_summary()

    # Initialize summary
    summary = base.copy()
    summary["Other Costs"] = 0.0
    summary["Sell Price"] = summary["Ingredients"].copy()

    # Apply stored overrides
    if not stored.empty:
        merged = summary.merge(stored, on="Meal", how="left", suffixes=("", "_ovr"))
        summary["Other Costs"] = merged["Other Costs_ovr"].fillna(summary["Other Costs"])
        summary["Sell Price"] = merged["Sell Price_ovr"].fillna(summary["Sell Price"])

    # Compute derived metrics
    summary["Total Cost"] = summary["Ingredients"] + summary["Other Costs"]
    summary["Profit Margin"] = summary["Sell Price"] - summary["Total Cost"]
    summary["Margin %"] = summary.apply(
        lambda r: (r["Profit Margin"] / r["Sell Price"] * 100) if r["Sell Price"] else 0.0,
        axis=1,
    )

    # Editable per-meal summary
    st.subheader("📦 Per-Meal Cost Summary")
    editor = st.data_editor(
        summary[["Meal", "Ingredients", "Other Costs", "Sell Price"]],
        key="cost_editor_final",
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Meal": st.column_config.TextColumn(disabled=True),
            "Ingredients": st.column_config.NumberColumn(format="$,.2f", disabled=True),
            "Other Costs": st.column_config.NumberColumn(format="$,.2f"),
            "Sell Price": st.column_config.NumberColumn(format="$,.2f"),
        },
    )

    # Final summary
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
    totals = {
        "Total Ingredient Cost": final["Ingredients"].sum(),
        "Total Other Costs": final["Other Costs"].sum(),
        "Total Cost": final["Total Cost"].sum(),
        "Total Sell Price": final["Sell Price"].sum(),
        "Total Profit": final["Profit Margin"].sum(),
        "Overall Margin %": (final["Profit Margin"].sum() / final["Sell Price"].sum() * 100)
            if final["Sell Price"].sum() else 0.0,
    }
    cols = st.columns(6)
    for idx, (label, value) in enumerate(totals.items()):
        fmt = f"${value:,.2f}" if "%" not in label else f"{value:.1f}%"
        cols[idx].metric(label, fmt)

    # Save button
    if st.button("💾 Save Costing Summary", key="save_summary_final"):
        save_summary_to_github(final[["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"]])
        st.success("✅ Costing summary saved and committed.")
