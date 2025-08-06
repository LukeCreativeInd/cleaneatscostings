import streamlit as st
import pandas as pd
import os

# ----------------------
# Config
# ----------------------
MEAL_SUMMARY_PATH = "data/stored_total_summary.csv"
BUSINESS_COSTS_PATH = "data/business_costs.csv"

# ----------------------
# Data loaders
# ----------------------
def load_meal_summary():
    """Load the meal summary totals from CSV."""
    if os.path.exists(MEAL_SUMMARY_PATH):
        df = pd.read_csv(MEAL_SUMMARY_PATH)
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.DataFrame(columns=["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"])


def load_business_costs():
    """Load business costs with Usage Factor."""
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
    Compute per-meal allocation for a single business cost line:
    - "per item": cost_per_meal = Amount * Usage Factor
    - "per month": cost_per_meal = Amount / meals_this_month
    - "per week": cost_per_meal = Amount / (meals_this_month / 4)
    - else: cost_per_meal = Amount / Usage Factor (if Usage Factor > 0)
    """
    amt = cost_row.get("Amount", 0) or 0
    usage = cost_row.get("Usage Factor", 0) or 0
    unit = cost_row.get("Unit", "per meal")
    try:
        if unit == "per item":
            return amt * usage
        if unit == "per month":
            meals_month = st.session_state.get("meals_this_month", 1)
            return amt / meals_month
        if unit == "per week":
            meals_month = st.session_state.get("meals_this_month", 1)
            # assume 4 weeks per month
            return amt / (meals_month / 4)
        return amt / usage if usage else 0.0
    except Exception:
        return 0.0

# ----------------------
# Main render
# ----------------------
def render():
    st.header("📊 Costing Dashboard")
    st.info("Overview of ingredient vs. business costs per meal and profitability.")

    # Allocation settings
    st.subheader("🧮 Allocation Settings")
    meals_this_month = st.number_input(
        "Meals produced this month", min_value=1, value=st.session_state.get("meals_this_month", 1000),
        help="Enter the total meals made this month to prorate monthly/weekly costs."
    )
    st.session_state["meals_this_month"] = meals_this_month

    # Load data
    meals_df = load_meal_summary()
    bc_df = load_business_costs()

    # Compute business allocation
    if not bc_df.empty:
        bc_df["Cost per Meal"] = bc_df.apply(compute_business_per_meal, axis=1)
        total_business = bc_df["Cost per Meal"].sum()
    else:
        total_business = 0.0

    # Assign business cost per meal to every meal
    meals_df["Business Cost"] = total_business

    # Recalculate combined cost & profit
    meals_df["Combined Cost"] = meals_df["Total Cost"] + meals_df["Business Cost"]
    meals_df["Profit"] = meals_df["Sell Price"] - meals_df["Combined Cost"]

    # Display key metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Avg Ingredient Cost", f"${meals_df['Total Cost'].mean():.2f}")
    col2.metric("Avg Business Cost", f"${meals_df['Business Cost'].mean():.2f}")
    col3.metric("Avg Profit", f"${meals_df['Profit'].mean():.2f}")

    # Detailed meal breakdown
    st.subheader("Meal Cost Breakdown")
    st.dataframe(
        meals_df[["Meal", "Total Cost", "Business Cost", "Combined Cost", "Sell Price", "Profit"]],
        use_container_width=True
    )

    # Business costs allocation table
    st.subheader("Business Costs Allocation")
    if bc_df.empty:
        st.write("No business costs defined.")
    else:
        st.dataframe(
            bc_df[["Name", "Cost Type", "Amount", "Unit", "Usage Factor", "Cost per Meal"]],
            use_container_width=True
        )
