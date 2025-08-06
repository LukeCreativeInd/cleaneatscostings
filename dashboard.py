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
    if os.path.exists(BUSINESS_COSTS_PATH):
        df = pd.read_csv(BUSINESS_COSTS_PATH)
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.DataFrame(columns=["Name", "Cost Type", "Amount", "Unit", "Usage Factor"])

# ----------------------
# Calculations
# ----------------------
def compute_business_per_meal(cost_row):
    """
    Compute per-meal allocation for a single business cost line.
    - For "per item": cost_per_meal = Amount * Usage Factor
    - Otherwise (per period): cost_per_meal = Amount / Usage Factor
    """
    amt = cost_row.get("Amount", 0)
    usage = cost_row.get("Usage Factor", 0)
    unit = cost_row.get("Unit", "per meal")
    try:
        if unit == "per item":
            return amt * usage
        # avoid division by zero
        return amt / usage if usage else 0.0
    except Exception:
        return 0.0

# ----------------------
# Main render
# ----------------------
def render():
    st.header("📊 Costing Dashboard")
    st.info("Overview of ingredient vs. business costs per meal and profitability.")

    # Load data
    meals_df = load_meal_summary()
    bc_df = load_business_costs()

    # Compute business allocation
    if not bc_df.empty:
        bc_df["Cost per Meal"] = bc_df.apply(compute_business_per_meal, axis=1)
        total_business = bc_df["Cost per Meal"].sum()
    else:
        total_business = 0.0

    # Assign business cost per meal
    meals_df["Business Cost"] = total_business

    # Recalc totals and profit
    meals_df["Combined Cost"] = meals_df["Total Cost"] + meals_df["Business Cost"]
    meals_df["Profit"] = meals_df["Sell Price"] - meals_df["Combined Cost"]

    # Display key metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Avg Ingredient Cost", f"${meals_df['Total Cost'].mean():.2f}")
    col2.metric("Avg Business Cost", f"${meals_df['Business Cost'].mean():.2f}")
    col3.metric("Avg Profit", f"${meals_df['Profit'].mean():.2f}")

    # Display detailed table
    st.subheader("Meal Cost Breakdown")
    st.dataframe(
        meals_df[["Meal", "Total Cost", "Business Cost", "Combined Cost", "Sell Price", "Profit"]],
        use_container_width=True
    )

    # Show raw business costs for reference
    st.subheader("Business Costs Allocation")
    if bc_df.empty:
        st.write("No business costs defined.")
    else:
        st.dataframe(bc_df[["Name", "Cost Type", "Amount", "Unit", "Usage Factor", "Cost per Meal"]], use_container_width=True)
