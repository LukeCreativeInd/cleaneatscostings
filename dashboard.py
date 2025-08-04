import streamlit as st
import pandas as pd
import os

MEALS_PATH = "data/meals.csv"
STORED_SUMMARY_PATH = "stored_total_summary.csv"


def load_stored_summary():
    if os.path.exists(STORED_SUMMARY_PATH):
        df = pd.read_csv(STORED_SUMMARY_PATH)
        # Normalize column names just in case
        df.columns = df.columns.str.strip().str.title()
        return df
    return pd.DataFrame(columns=["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"])


def render():
    st.header("💰 Costing Dashboard")

    # Load any existing stored summary (other costs / sell price history)
    stored_summary = load_stored_summary()

    if os.path.exists(MEALS_PATH):
        meals_df = pd.read_csv(MEALS_PATH)
        if not meals_df.empty:
            # Aggregate ingredient cost per meal
            ingredient_costs = (
                meals_df.groupby("Meal")["Total Cost"]
                .sum()
                .reset_index()
                .rename(columns={"Total Cost": "Ingredients"})
            )

            # Merge with previously saved other costs / sell price
            merged = ingredient_costs.merge(
                stored_summary[["Meal", "Other Costs", "Sell Price"]],
                on="Meal",
                how="left",
            )

            # Defaults
            merged["Other Costs"] = merged["Other Costs"].fillna(0.0)
            # Default sell price to Ingredients + Other Costs if missing
            merged["Sell Price"] = merged["Sell Price"].fillna(
                merged["Ingredients"] + merged["Other Costs"]
            )

            # Compute total cost and margins
            merged["Total Cost"] = merged["Ingredients"] + merged["Other Costs"]
            merged["Profit Margin"] = merged["Sell Price"] - merged["Total Cost"]

            def compute_margin_pct(row):
                if row["Sell Price"] and row["Sell Price"] != 0:
                    return (row["Profit Margin"] / row["Sell Price"]) * 100
                return 0.0

            merged["Margin %"] = merged.apply(compute_margin_pct, axis=1)

            # Keep canonical meal + ingredient cost to reapply after edits
            base_ingredients = merged.set_index("Meal")["Ingredients"].to_dict()

            st.subheader("📦 Per-Meal Cost Summary")
            st.markdown(
                "Edit **Other Costs** and **Sell Price** below. **Total Cost**, **Profit Margin**, and **Margin %** are recalculated automatically."
            )

            # Prepare editable slice
            editable = merged[["Meal", "Ingredients", "Other Costs", "Sell Price"]].copy()

            edited = st.data_editor(
                editable,
                num_rows="dynamic",
                use_container_width=True,
                key="costing_editor",
                column_config={
                    "Meal": st.column_config.TextColumn("Meal", disabled=True),
                    "Ingredients": st.column_config.NumberColumn(
                        "Ingredients", format="$ %.2f", disabled=True
                    ),
                    "Other Costs": st.column_config.NumberColumn(
                        "Other Costs", format="$ %.2f"
                    ),
                    "Sell Price": st.column_config.NumberColumn(
                        "Sell Price", format="$ %.2f"
                    ),
                },
            )

            # Recompute derived fields from edited input
            edited["Ingredients"] = edited["Meal"].map(base_ingredients)
            edited["Total Cost"] = edited["Ingredients"] + edited["Other Costs"]
            edited["Profit Margin"] = edited["Sell Price"] - edited["Total Cost"]
            edited["Margin %"] = edited.apply(
                lambda r: (r["Profit Margin"] / r["Sell Price"] * 100)
                if r["Sell Price"] and r["Sell Price"] != 0
                else 0.0,
                axis=1,
            )

            # Display the full view with formatting
            display_df = edited[
                ["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price", "Profit Margin", "Margin %"]
            ].copy()

            st.markdown("### Finalized Summary")
            st.dataframe(
                display_df.style.format(
                    {
                        "Ingredients": "$ {:.2f}",
                        "Other Costs": "$ {:.2f}",
                        "Total Cost": "$ {:.2f}",
                        "Sell Price": "$ {:.2f}",
                        "Profit Margin": "$ {:.2f}",
                        "Margin %": "{:.1f}%",
                    }
                ),
                use_container_width=True,
            )

            # Overall totals
            total_ingredients = display_df["Ingredients"].sum()
            total_other = display_df["Other Costs"].sum()
            total_cost = display_df["Total Cost"].sum()
            total_sell = display_df["Sell Price"].sum()
            total_profit = display_df["Profit Margin"].sum()
            overall_margin_pct = (
                (total_profit / total_sell * 100) if total_sell and total_sell != 0 else 0.0
            )

            st.markdown("#### Aggregate Metrics")
            cols = st.columns(6)
            cols[0].metric("Total Ingredient Cost", f"${total_ingredients:,.2f}")
            cols[1].metric("Total Other Costs", f"${total_other:,.2f}")
            cols[2].metric("Total Cost", f"${total_cost:,.2f}")
            cols[3].metric("Total Sell Price", f"${total_sell:,.2f}")
            cols[4].metric("Total Profit", f"${total_profit:,.2f}")
            cols[5].metric("Overall Margin %", f"{overall_margin_pct:.1f}%")

            # Save summary
            if st.button("💾 Save Costing Summary"):
                # Reconstruct the canonical stored summary format
                final_df = display_df[["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"]].copy()
                st.session_state.total_df = final_df
                try:
                    from app import save_data

                    save_data(final_df)
                    st.success("✅ Summary saved and persisted."); st.experimental_rerun()
                except Exception as e:
                    st.error(f"Failed to save summary: {e}")
        else:
            st.warning("No meals found in meals.csv. Build a meal in the Meals tab to populate costs.")
    else:
        st.warning("📂 No meal data yet. You can upload one-time data below to initialise.")
        uploaded_file = st.file_uploader(
            "Initialise from costing spreadsheet (one-time import)",
            type=["xlsx"],
            key="dashboard_file_upload",
        )
        if uploaded_file:
            try:
                raw_df = pd.read_excel(uploaded_file, sheet_name="TOTAL")
                raw_df = raw_df.rename(
                    columns={
                        "DESCRIPTION MEAL": "Meal",
                        "RAW MATERIAL": "Ingredients",
                        "ROADMAP": "Other Costs",
                        "TOTAL": "Total Cost",
                        "SELL COST": "Sell Price",
                    }
                )
                clean_df = raw_df[["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"]]
                st.session_state.total_df = clean_df
                from app import save_data

                save_data(clean_df)
                st.success("✅ Data imported and saved!")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ Failed to load spreadsheet: {e}")
