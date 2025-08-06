import streamlit as st
import pandas as pd
import os
import uuid

MEAL_DATA_PATH = "data/meals.csv"
INGREDIENTS_PATH = "data/ingredients.csv"

# Unit conversion utilities

def display_to_base(qty, display_unit, base_unit_type):
    t = (base_unit_type or "").upper()
    u = (display_unit or "").lower()
    if t == "KG":
        if u == "kg": return qty * 1000
        if u == "g": return qty
    if t == "L":
        if u == "l": return qty * 1000
        if u == "ml": return qty
    return qty


def base_to_display(qty, base_unit_type, display_unit):
    t = (base_unit_type or "").upper()
    u = (display_unit or "").lower()
    if t == "KG":
        if u == "kg": return qty / 1000, "kg"
        if u == "g": return qty, "g"
    if t == "L":
        if u == "l": return qty / 1000, "L"
        if u == "ml": return qty, "ml"
    return qty, display_unit


def get_display_unit_options(base_unit_type):
    t = (base_unit_type or "").upper()
    if t == "KG": return ["kg", "g"]
    if t == "L": return ["L", "ml"]
    return ["unit"]

# Data loaders

def load_meals():
    if os.path.exists(MEAL_DATA_PATH):
        return pd.read_csv(MEAL_DATA_PATH)
    return pd.DataFrame(columns=["Meal", "Ingredient", "Quantity", "Cost per Unit", "Total Cost", "Input Unit", "Sell Price"])


def load_ingredients():
    if os.path.exists(INGREDIENTS_PATH):
        return pd.read_csv(INGREDIENTS_PATH)
    return pd.DataFrame(columns=["Ingredient", "Unit Type", "Cost per Unit"])

# Main UI

def render():
    st.header("🍽️ Meal Builder")
    st.info("Build meals by adding ingredients & set a sell price; then save and edit existing meals.")

    meals_df = load_meals()
    ing_df = load_ingredients()
    opts = sorted(ing_df["Ingredient"].unique())

    # Session state defaults
    st.session_state.setdefault("meal_name", "")
    st.session_state.setdefault("meal_sell_price", 0.0)
    st.session_state.setdefault(
        "meal_ingredients",
        pd.DataFrame(columns=["Ingredient", "Quantity", "Cost per Unit", "Total Cost", "Input Unit"])
    )
    st.session_state.setdefault("meal_form_key", str(uuid.uuid4()))
    st.session_state.setdefault("editing_meal", None)

    # New meal form
    with st.form(key=st.session_state["meal_form_key"]):
        st.text_input("Meal Name", key="meal_name")
        st.number_input("Sell Price", min_value=0.0, step=0.01, key="meal_sell_price")
        new_i = st.selectbox("Ingredient", opts, key="new_ing")
        new_q = st.number_input("Qty", min_value=0.0, step=0.1, key="new_qty")
        base = ing_df[ing_df["Ingredient"] == new_i]
        unit_opts = get_display_unit_options(base.iloc[0]["Unit Type"]) if not base.empty else ["unit"]
        new_u = st.selectbox("Unit", unit_opts, key="new_unit")
        if st.form_submit_button("➕ Add Ingredient"):
            if not st.session_state["meal_name"].strip():
                st.warning("Enter a meal name first.")
            else:
                row = base.iloc[0]
                bq = display_to_base(new_q, new_u, row["Unit Type"])
                tot = round(bq * float(row["Cost per Unit"]), 6)
                newrow = {
                    "Ingredient": new_i,
                    "Quantity": bq,
                    "Cost per Unit": float(row["Cost per Unit"]),
                    "Total Cost": tot,
                    "Input Unit": new_u
                }
                df0 = st.session_state["meal_ingredients"]
                st.session_state["meal_ingredients"] = pd.concat([df0, pd.DataFrame([newrow])], ignore_index=True)
                # reset fields
                st.session_state["new_ing"] = opts[0]
                st.session_state["new_qty"] = 0.0
                st.session_state["new_unit"] = unit_opts[0]

    # Preview unsaved ingredients
    if not st.session_state["meal_ingredients"].empty:
        st.subheader(f"🧾 Ingredients for '{st.session_state['meal_name']}' (unsaved)")
        df = st.session_state["meal_ingredients"].copy()
        df["Display"] = df.apply(
            lambda r: f"{base_to_display(r['Quantity'], r['Input Unit'], r['Input Unit'])[0]:.2f} {r['Input Unit']}",
            axis=1
        )
        st.table(df[["Ingredient", "Display", "Total Cost"]])

    # Edit existing meals
    for mn in meals_df["Meal"].unique():
        if st.session_state["editing_meal"] != mn:
            if st.button(f"✏️ {mn}", key=f"btn_{mn}"):
                st.session_state["editing_meal"] = mn
                st.session_state[f"edit_{mn}"] = meals_df[meals_df['Meal'] == mn].reset_index(drop=True)
        else:
            df_edit = st.session_state[f"edit_{mn}"]
            with st.expander(f"Edit Meal {mn}", expanded=True):
                # Delete meal button
                if st.button("🗑️ Delete Meal", key=f"del_{mn}"):
                    remaining = meals_df[meals_df['Meal'] != mn]
                    os.makedirs(os.path.dirname(MEAL_DATA_PATH), exist_ok=True)
                    remaining.to_csv(MEAL_DATA_PATH, index=False)
                    st.success(f"Deleted meal {mn}")
                    st.session_state['editing_meal'] = None
                    return

                nm = st.text_input("Meal Name", value=mn, key=f"rename_{mn}")
                pr = st.number_input(
                    "Sell Price",
                    min_value=0.0,
                    step=0.01,
                    value=float(meals_df.loc[meals_df['Meal']==mn, 'Sell Price'].iloc[0]),
                    key=f"sellprice_{mn}"
                )
                st.markdown("### Ingredients")
                for idx, r in df_edit.iterrows():
                    cols = st.columns([3, 2, 2, 1, 1])
                    cols[0].write(r["Ingredient"])
                    qty_val, _ = base_to_display(r['Quantity'], r['Input Unit'], r['Input Unit'])
                    q = cols[1].number_input(
                        "Qty",
                        value=qty_val,
                        min_value=0.0,
                        step=0.1,
                        key=f"qty_{mn}_{idx}"
                    )
                    unit_opts = get_display_unit_options(r['Input Unit'])
                    us = cols[2].selectbox(
                        "Unit",
                        unit_opts,
                        index=unit_opts.index(r['Input Unit']),
                        key=f"unit_{mn}_{idx}"
                    )
                    bq2 = display_to_base(q, us, r['Input Unit'])
                    tot2 = round(bq2 * float(r['Cost per Unit']), 6)
                    cols[3].write(f"Cost: ${tot2}")
                    if cols[4].button("Remove", key=f"rem_{mn}_{idx}"):
                        df_edit = df_edit.drop(idx).reset_index(drop=True)
                        st.session_state[f"edit_{mn}"] = df_edit

                st.markdown("### Add Ingredient")
                a1, a2, a3, a4 = st.columns([3, 2, 2, 1])
                new_i = a1.selectbox("Ingredient", opts, key=f"new_ing_{mn}")
                new_q = a2.number_input("Qty", min_value=0.0, step=0.1, key=f"new_qty_{mn}")
                base2 = ing_df[ing_df["Ingredient"] == new_i]
                uops = get_display_unit_options(base2.iloc[0]["Unit Type"]) if not base2.empty else ["unit"]
                new_u = a3.selectbox("Unit", uops, key=f"new_unit_{mn}")
                if a4.button("➕ Add", key=f"add_{mn}"):
                    row2 = base2.iloc[0]
                    bq3 = display_to_base(new_q, new_u, row2["Unit Type"])
                    tot3 = round(bq3 * float(row2["Cost per Unit"]), 6)
                    newrow = {
                        "Ingredient": new_i,
                        "Quantity": bq3,
                        "Cost per Unit": float(row2["Cost per Unit"]),
                        "Total Cost": tot3,
                        "Input Unit": new_u
                    }
                    st.session_state[f"edit_{mn}"] = pd.concat([df_edit, pd.DataFrame([newrow])], ignore_index=True)
                    # reset fields
                    st.session_state[f"new_ing_{mn}"] = opts[0]
                    st.session_state[f"new_qty_{mn}"] = 0.0
                    st.session_state[f"new_unit_{mn}"] = uops[0]

                if st.button("💾 Save Changes", key=f"sv_{mn}"):
                    df_edit = st.session_state[f"edit_{mn}"]
                    df_edit["Meal"] = nm.strip() or mn
                    df_edit["Sell Price"] = pr
                    others = meals_df[meals_df['Meal'] != mn]
                    out = pd.concat([others, df_edit], ignore_index=True)
                    os.makedirs(os.path.dirname(MEAL_DATA_PATH), exist_ok=True)
                    out.to_csv(MEAL_DATA_PATH, index=False)
                    st.success(f"✅ Saved {df_edit['Meal'].iloc[0]}")
                    st.session_state['editing_meal'] = None

if __name__ == "__main__":
    render()
