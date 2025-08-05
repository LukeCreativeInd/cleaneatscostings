import streamlit as st
import pandas as pd
import os
import requests
import base64
from datetime import datetime

MEALS_PATH = "data/meals.csv"
SUMMARY_PATH = "data/stored_total_summary.csv"


def load_stored_summary():
    if os.path.exists(SUMMARY_PATH):
        df = pd.read_csv(SUMMARY_PATH)
        df.columns = df.columns.str.strip().str.title()
        return df
    return pd.DataFrame(columns=["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"])


def save_summary_to_github(df: pd.DataFrame):
    """Commit data/stored_total_summary.csv to GitHub using your existing pattern."""
    os.makedirs(os.path.dirname(SUMMARY_PATH), exist_ok=True)
    df.to_csv(SUMMARY_PATH, index=False)
    try:
        token = st.secrets["github_token"]
        repo = st.secrets["github_repo"]
        branch = st.secrets.get("github_branch", "main")
    except KeyError:
        st.warning("GitHub secrets missing; summary saved locally but not pushed.")
        return

    repo_path = SUMMARY_PATH  # commit as data/stored_total_summary.csv
    api_url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    # Try to get existing file SHA
    resp = requests.get(api_url, headers=headers, params={"ref": branch})
    sha = resp.json().get("sha") if resp.status_code == 200 else None

    content = base64.b64encode(df.to_csv(index=False).encode()).decode()
    payload = {
        "message": f"Update costing summary at {datetime.utcnow().isoformat()}Z",
        "content": content,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    put = requests.put(api_url, headers=headers, json=payload)
    if put.status_code in (200, 201):
        st.success("✅ Costing summary committed to GitHub")
    else:
        st.error(f"GitHub commit failed ({put.status_code}): {put.text}")


def render():
    st.header("💰 Costing Dashboard")

    stored_summary = load_stored_summary()

    if os.path.exists(MEALS_PATH):
        meals_df = pd.read_csv(MEALS_PATH)
        if not meals_df.empty:
            # Aggregate base ingredient costs
            agg = (
                meals_df.groupby("Meal")["Total Cost"].sum()
                .reset_index()
                .rename(columns={"Total Cost": "Ingredients"})
            )
            merged = agg.merge(
                stored_summary[["Meal", "Other Costs", "Sell Price"]],
                on="Meal", how="left"
            )
            merged["Other Costs"] = merged["Other Costs"].fillna(0.0)
            merged["Sell Price"] = merged["Sell Price"].fillna(
                merged["Ingredients"] + merged["Other Costs"]
            )
            merged["Total Cost"] = merged["Ingredients"] + merged["Other Costs"]
            merged["Profit Margin"] = merged["Sell Price"] - merged["Total Cost"]
            merged["Margin %"] = merged.apply(
                lambda r: (r["Profit Margin"]/r["Sell Price"]*100) if r["Sell Price"] else 0.0,
                axis=1
            )

            st.subheader("📦 Per-Meal Cost Summary")
            st.markdown("Edit Other Costs & Sell Price below. Totals recalc.")

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
            # compute derived
            edited["Total Cost"] = edited["Ingredients"] + edited["Other Costs"]
            edited["Profit Margin"] = edited["Sell Price"] - edited["Total Cost"]
            edited["Margin %"] = edited.apply(
                lambda r: (r["Profit Margin"]/r["Sell Price"]*100) if r["Sell Price"] else 0.0,
                axis=1
            )

            display_df = edited.copy()
            st.subheader("Finalized Summary")
            st.dataframe(
                display_df.style.format({
                    "Ingredients": "${:.2f}",
                    "Other Costs": "${:.2f}",
                    "Total Cost": "${:.2f}",
                    "Sell Price": "${:.2f}",
                    "Profit Margin": "${:.2f}",
                    "Margin %": "{:.1f}%",
                }),
                use_container_width=True,
            )

            # metrics
            total_ing = display_df["Ingredients"].sum()
            total_other = display_df["Other Costs"].sum()
            total_cost = display_df["Total Cost"].sum()
            total_sell = display_df["Sell Price"].sum()
            total_profit = display_df["Profit Margin"].sum()
            overall_pct = (total_profit/total_sell*100) if total_sell else 0.0

            cols = st.columns(6)
            cols[0].metric("Total Ingredient Cost", f"${total_ing:,.2f}")
            cols[1].metric("Total Other Costs", f"${total_other:,.2f}")
            cols[2].metric("Total Cost", f"${total_cost:,.2f}")
            cols[3].metric("Total Sell Price", f"${total_sell:,.2f}")
            cols[4].metric("Total Profit", f"${total_profit:,.2f}")
            cols[5].metric("Overall Margin %", f"{overall_pct:.1f}%")

            if st.button("💾 Save Costing Summary", key="save_summary"):
                final = display_df[["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"]].copy()
                st.session_state.total_df = final
                from app import save_data
                save_data(final)
                st.success("✅ Summary saved locally")
                save_summary_to_github(final)
        else:
            st.warning("No meals in data. Build some meals first.")
    else:
        st.warning("No meal data file found.")
        uploaded = st.file_uploader("Import costing sheet", type=["xlsx"], key="import_dash")
        if uploaded:
            try:
                raw = pd.read_excel(uploaded, sheet_name="TOTAL")
                raw = raw.rename(columns={
                    "DESCRIPTION MEAL": "Meal",
                    "RAW MATERIAL": "Ingredients",
                    "ROADMAP": "Other Costs",
                    "TOTAL": "Total Cost",
                    "SELL COST": "Sell Price",
                })
                clean = raw[["Meal","Ingredients","Other Costs","Total Cost","Sell Price"]]
                st.session_state.total_df = clean
                from app import save_data
                save_data(clean)
                st.success("✅ Imported and saved")
                save_summary_to_github(clean)
            except Exception as e:
                st.error(f"Import failed: {e}")
