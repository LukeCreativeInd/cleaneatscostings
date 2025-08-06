import streamlit as st
import pandas as pd
import os

# ----------------------
# Config
# ----------------------
MEAL_SUMMARY_PATH   = "data/stored_total_summary.csv"
BUSINESS_COSTS_PATH = "data/business_costs.csv"

# ----------------------
# Data loaders
# ----------------------
def load_meal_summary():
    """
    Generate the meal summary by:
      1) Summing up Total Cost from data/meals.csv into an Ingredients column
      2) Merging in stored Other Costs & Sell Price overrides
      3) Filling defaults and computing Total Cost = Ingredients + Other Costs
    """
    meals_path = "data/meals.csv"

    # 1) Ingredient aggregation
    if os.path.exists(meals_path):
        mdf = pd.read_csv(meals_path)
        mdf.columns = [c.strip() for c in mdf.columns]
        ing_totals = (
            mdf.groupby("Meal")["Total Cost"]
               .sum()
               .reset_index()
               .rename(columns={"Total Cost": "Ingredients"})
        )
    else:
        ing_totals = pd.DataFrame({"Meal": [], "Ingredients": []})

    # 2) Stored overrides
    if os.path.exists(MEAL_SUMMARY_PATH):
        stored = pd.read_csv(MEAL_SUMMARY_PATH)
        stored.columns = [c.strip() for c in stored.columns]
    else:
        stored = pd.DataFrame(columns=["Meal", "Other Costs", "Sell Price"])

    # 3) Merge & fill
    summary = pd.merge(ing_totals, stored, on="Meal", how="outer")
    summary["Ingredients"]  = summary.get("Ingredients", 0).fillna(0)
    summary["Other Costs"]  = summary.get("Other Costs", 0).fillna(0)
    summary["Sell Price"]   = summary.get("Sell Price", summary["Ingredients"]).fillna(summary["Ingredients"])
    summary["Total Cost"]   = summary["Ingredients"] + summary["Other Costs"]

    return summary

def load_business_costs():
    """
    Load business costs, ensuring the key columns exist.
    """
    cols = ["Name", "Cost Type", "Amount", "Unit", "Usage Factor"]
    if os.path.exists(BUSINESS_COSTS_PATH):
        df = pd.read_csv(BUSINESS_COSTS_PATH)
        df.columns = [c.strip() for c in df.columns]
        for c in cols:
            if c not in df.columns:
                df[c] = 0 if c in ["Amount", "Usage Factor"] else ""
        return df[cols]
    return pd.DataFrame(columns=cols)

# ----------------------
# Calculations
# ----------------------
def compute_business_per_meal(cost_row):
    """
    Compute per-meal allocation from one cost line:
      • per item  => Amount * Usage Factor  (items per meal)
      • per meal  => Amount                 (flat per meal)
      • per month => Amount / meals_this_month
      • per week  => Amount / (meals_this_month / 4)
      • otherwise => Amount / Usage Factor
    """
    amt   = cost_row.get("Amount", 0) or 0
    usage = cost_row.get("Usage Factor", 0) or 0
    unit  = cost_row.get("Unit", "per meal")

    try:
        if unit == "per item":
            return amt * usage
        if unit == "per meal":
            return amt
        if unit == "per month":
            m = st.session_state.get("meals_this_month", 1)
            return amt / m
        if unit == "per week":
            m = st.session_state.get("meals_this_month", 1)
            return amt / (m / 4)
        return amt / usage if usage else 0.0
    except:
        return 0.0

# ----------------------
# Main render
# ----------------------
def render():
    st.header("📊 Costing Dashboard")
    st.info("Overview of ingredient vs. business costs per meal and profitability.")

    # — Allocation Settings —
    st.subheader("🧮 Allocation Settings")
    meals_month = st.number_input(
        "Meals produced this month",
        min_value=1,
        value=st.session_state.get("meals_this_month", 1000),
        help="Total meals in the month for prorating monthly/weekly costs.",
    )
    st.session_state["meals_this_month"] = meals_month

    # — Load Data —
    meals_df = load_meal_summary()
    bc_df    = load_business_costs()

    # — Compute Overhead per Meal —
    if not bc_df.empty:
        bc_df["Cost per Meal"] = bc_df.apply(compute_business_per_meal, axis=1)
        total_business         = bc_df["Cost per Meal"].sum()
    else:
        total_business = 0.0

    # — Assign & Recompute —
    meals_df["Business Cost"] = total_business
    meals_df["Combined Cost"] = meals_df["Total Cost"] + total_business
    meals_df["Profit"]        = meals_df["Sell Price"] - meals_df["Combined Cost"]

    # — Metrics Cards —
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Ingredient Cost", f"${meals_df['Ingredients'].mean():.2f}")
    c2.metric("Avg Business Cost",    f"${meals_df['Business Cost'].mean():.2f}")
    c3.metric("Avg Profit",           f"${meals_df['Profit'].mean():.2f}")

    # — Detailed Table —
    st.subheader("Meal Cost Breakdown")
    st.dataframe(
        meals_df[["Meal", "Ingredients", "Business Cost", "Combined Cost", "Sell Price", "Profit"]],
        use_container_width=True,
    )

    # — Business Costs Drill-down —
    st.subheader("Business Costs Allocation")
    if bc_df.empty:
        st.write("No business costs defined.")
    else:
        st.dataframe(
            bc_df[["Name", "Cost Type", "Amount", "Unit", "Usage Factor", "Cost per Meal"]],
            use_container_width=True,
        )
