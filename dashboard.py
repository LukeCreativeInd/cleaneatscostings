import streamlit as st
import pandas as pd

def render():
    st.header("💰 Costing Dashboard")
    df = st.session_state.total_df.copy()

    if not df.empty:
        df["Profit Margin"] = df["Sell Price"] - df["Total Cost"]
        df["Margin %"] = (df["Profit Margin"] / df["Sell Price"]) * 100
        st.dataframe(df.style.format({
            "Ingredients": "$ {:.2f}",
            "Other Costs": "$ {:.2f}",
            "Total Cost": "$ {:.2f}",
            "Sell Price": "$ {:.2f}",
            "Profit Margin": "$ {:.2f}",
            "Margin %": "{:.1f}%"
        }), use_container_width=True)

    else:
        st.warning("📂 No costing data yet. You can upload one-time data below to initialise.")

        uploaded_file = st.file_uploader(
            "Initialise from costing spreadsheet (one-time import)",
            type=["xlsx"],
            key="dashboard_file_upload"
        )

        if uploaded_file:
            try:
                raw_df = pd.read_excel(uploaded_file, sheet_name="TOTAL")
                raw_df = raw_df.rename(columns={
                    "DESCRIPTION MEAL": "Meal",
                    "RAW MATERIAL": "Ingredients",
                    "ROADMAP": "Other Costs",
                    "TOTAL": "Total Cost",
                    "SELL COST": "Sell Price"
                })
                clean_df = raw_df[["Meal", "Ingredients", "Other Costs", "Total Cost", "Sell Price"]]
                st.session_state.total_df = clean_df
                from app import save_data
                save_data(clean_df)
                st.success("✅ Data imported and saved!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to load spreadsheet: {e}")
