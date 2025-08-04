import streamlit as st
import pandas as pd
import os
import requests
import base64
from datetime import datetime
from io import StringIO

MEAL_DATA_PATH = "data/meals.csv"
INGREDIENTS_PATH = "data/ingredients.csv"


# ----------------------
# Unit conversion utils
# ----------------------
def display_to_base(qty, display_unit, base_unit_type):
    base_unit_type = (base_unit_type or "").upper()
    unit = (display_unit or "").lower()
    if base_unit_type == "KG":
        if unit in ["g", "gram", "grams"]:
            return qty / 1000.0
        else:  # assume kg
            return qty
    if base_unit_type == "L":
        if unit in ["ml"]:
            return qty / 1000.0
        else:  # assume L
            return qty
    if base_unit_type == "UNIT":
        return qty
    # fallback: no conversion
    return qty


def base_to_display(qty_base, base_unit_type):
    base_unit_type = (base_unit_type or "").upper()
    if base_unit_type == "KG":
        if qty_base < 1:
            return qty_base * 1000.0, "g"
        else:
            return qty_base, "kg"
    if base_unit_type == "L":
        if qty_base < 1:
            return qty_base * 1000.0, "ml"
        else:
            return qty_base, "L"
    if base_unit_type == "UNIT":
        return qty_base, "unit"
    return qty_base, ""


def get_display_unit_options(base_unit_type):
    base_unit_type = (base_unit_type or "").upper()
    if base_unit_type == "KG":
        return ["kg", "g"]
    if base_unit_type == "L":
        return ["L", "ml"]
    if base_unit_type == "UNIT":
        return ["unit"]
    return [""]


# ----------------------
# Data loading helpers
# ----------------------
def load_meals():
    if os.path.exists(MEAL_DATA_PATH):
        df = pd.read_csv(MEAL_DATA_PATH)
        # unify column names
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.DataFrame(
        columns=[
            "Meal",
            "Ingredient",
            "Quantity",  # in base units
            "Cost per Unit",
            "Total Cost",
            "Input Unit",  # optional: display unit used (e.g., g, kg)
        ]
    )


def load_ingredients():
    if os.path.exists(INGREDIENTS_PATH):
        df = pd.read_csv(INGREDIENTS_PATH)
        df.columns = [c.strip().title() for c in df.columns]

        # Ensure expected columns exist
        if "Ingredient" not in df.columns:
            df["Ingredient"] = ""
        if "Unit Type" not in df.columns:
            df["Unit Type"] = ""
        if "Purchase Size" not in df.columns:
            df["Purchase Size"] = 1.0
        if "Cost" not in df.columns:
            df["Cost"] = 0.0

        # Compute cost per unit if missing
        if "Cost Per Unit" not in df.columns:
            def cpu_calc(r):
                try:
                    ps = float(r.get("Purchase Size", 1))
                    c = float(r.get("Cost", 0))
                    return round(c / ps, 6) if ps != 0 else 0
                except Exception:
                    return 0
            df["Cost Per Unit"] = df.apply(cpu_calc, axis=1)

        # Normalize text
        df["Ingredient"] = df["Ingredient"].astype(str).str.strip().str.title()
        df["Unit Type"] = df["Unit Type"].astype(str).str.strip().str.upper()
        return df
    # fallback skeleton
    return pd.DataFrame(
        columns=["Ingredient", "Unit Type", "Purchase Size", "Cost", "Cost Per Unit"]
    )


# ----------------------
# GitHub commit helper
# ----------------------
def commit_file_to_github(local_path: str, repo_path: str, message_prefix: str):
    """Mirrors the pattern used elsewhere: commits a file to GitHub if secrets exist."""
    try:
        token = st.secrets["github_token"]
        repo = st.secrets["github_repo"]
        branch = st.secrets.get("github_branch", "main")
    except KeyError:
        st.warning("GitHub secrets missing; saved locally but did not push to repo.")
        return

    api_url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    # Read local file content
    with open(local_path, "rb") as f:
        raw = f.read()
    content_b64 = base64.b64encode(raw).decode()

    # Check existing file to get sha if present
    get_resp = requests.get(api_url, headers=headers, params={"ref": branch})
    sha = None
    if get_resp.status_code == 200:
        try:
            sha = get_resp.json().get("sha")
        except Exception:
            sha = None

    payload = {
        "message": f"{message_prefix} at {datetime.utcnow().isoformat()}Z",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    put_resp = requests.put(api_url, headers=headers, json=payload)
    if put_resp.status_code not in (200, 201):
        st.error(f"GitHub commit failed: {put_resp.status_code} {put_resp.text}")
    else:
        st.success(f"✅ {os.path.basename(repo_path)} committed to GitHub")


# ----------------------
# Core rendering
# ----------------------
def render():
    st.header("🍽️ Meal Builder")
    st.info(
        """Build meals by adding ingredients with quantities. 
You can edit existing meals, rename them, and specify meal-level units (e.g., 150g of pasta from a 10kg bag)."""
    )

    # Load data
    meals_df = load_meals()
    ingredients_df = load_ingredients()

    # Prepare ingredient dropdown
    ingredient_options = sorted(ingredients_df["Ingredient"].dropna().unique())

    # Session state defaults for new meal
    st.session_state.setdefault("meal_name", "")
    st.session_state.setdefault(
        "meal_ingredients",
        pd.DataFrame(
            columns=[
                "Ingredient",
                "Quantity",  # base unit
                "Cost per Unit",
                "Total Cost",
                "Input Unit",
            ]
        ),
    )
    st.session_state.setdefault("new_meal_qty", 0.0)
    st.session_state.setdefault("new_meal_unit", None)
    if "new_meal_ingredient" not in st.session_state:
        st.session_state.new_meal_ingredient = ingredient_options[0] if ingredient_options else ""

    # ----------------------
    # Add new meal section
    # ----------------------
    st.subheader("Create / Add Meal")
    with st.form("new_meal_form", clear_on_submit=False):
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        with col1:
            st.text_input("Meal Name", key="meal_name")
        with col2:
            st.selectbox(
                "Ingredient",
                options=ingredient_options,
                key="new_meal_ingredient",
                help="Select ingredient to add to this meal",
            )
        with col3:
            # Look up base unit info for selected ingredient
            selected = st.session_state.new_meal_ingredient
            info = ingredients_df[
                ingredients_df["Ingredient"].str.lower() == str(selected).strip().lower()
            ]
            if not info.empty:
                base_unit = info.iloc[0].get("Unit Type", "")
            else:
                base_unit = ""
            unit_opts = get_display_unit_options(base_unit)
            st.number_input(
                "Qty",
                min_value=0.0,
                step=0.1,
                key="new_meal_qty",
                help=f"Quantity in {', '.join(unit_opts) if unit_opts else 'base unit'}",
            )
            if st.session_state.new_meal_unit is None:
                st.session_state.new_meal_unit = unit_opts[0] if unit_opts else ""
            st.selectbox(
                "Unit",
                options=unit_opts,
                key="new_meal_unit",
                label_visibility="collapsed",
            )
        with col4:
            submitted = st.form_submit_button("➕ Add Ingredient to Meal")

        if submitted:
            meal_name = st.session_state.meal_name.strip()
            if not meal_name:
                st.warning("Please provide a meal name before adding ingredients.")
            else:
                ingredient = st.session_state.new_meal_ingredient
                qty = st.session_state.new_meal_qty
                input_unit = st.session_state.new_meal_unit
                if qty <= 0:
                    st.warning("Quantity must be greater than zero.")
                else:
                    # Lookup ingredient row
                    match = ingredients_df[
                        ingredients_df["Ingredient"].str.lower() == str(ingredient).strip().lower()
                    ]
                    if match.empty:
                        st.error(f"Ingredient '{ingredient}' not found.")
                    else:
                        row = match.iloc[0]
                        base_unit_type = row.get("Unit Type", "")
                        cpu = float(row.get("Cost Per Unit", 0.0))
                        # Convert display to base
                        qty_base = display_to_base(qty, input_unit, base_unit_type)
                        total_cost = round(qty_base * cpu, 6)
                        new_entry = {
                            "Ingredient": ingredient,
                            "Quantity": qty_base,
                            "Cost per Unit": cpu,
                            "Total Cost": total_cost,
                            "Input Unit": input_unit,
                        }
                        # Append to meal_ingredients
                        current = st.session_state.meal_ingredients.copy()
                        new_df = pd.concat([current, pd.DataFrame([new_entry])], ignore_index=True)
                        st.session_state.meal_ingredients = new_df
                        st.success(f"Added {qty}{input_unit} of {ingredient} to '{meal_name}'.")

    # Show unsaved current meal ingredients
    if not st.session_state.meal_ingredients.empty:
        st.subheader(f"🧾 Ingredients for '{st.session_state.meal_name}' (unsaved)")
        display_temp = st.session_state.meal_ingredients.copy()
        # Show human-friendly quantity in display units
        def annotate_display(row):
            # base quantity is row["Quantity"], find its display form based on ingredient unit type
            ingredient = row["Ingredient"]
            info = ingredients_df[
                ingredients_df["Ingredient"].str.lower() == str(ingredient).strip().lower()
            ]
            base_unit_type = info.iloc[0].get("Unit Type", "") if not info.empty else ""
            qty_display, unit_display = base_to_display(row["Quantity"], base_unit_type)
            return f"{qty_display:.2f} {unit_display}"

        display_temp["Display Quantity"] = display_temp.apply(annotate_display, axis=1)
        st.dataframe(
            display_temp[
                ["Ingredient", "Display Quantity", "Cost per Unit", "Total Cost"]
            ],
            use_container_width=True,
        )

        # Save the meal (new meal)
        if st.button("💾 Save Meal"):
            meal_name = st.session_state.meal_name.strip()
            if not meal_name:
                st.warning("Meal name is required.")
            elif st.session_state.meal_ingredients.empty:
                st.warning("Add at least one ingredient.")
            else:
                try:
                    # Build meal rows
                    saved = meals_df.copy()
                    new_meal_df = st.session_state.meal_ingredients.copy()
                    new_meal_df.insert(0, "Meal", meal_name)
                    combined = pd.concat([saved, new_meal_df], ignore_index=True)
                    os.makedirs("data", exist_ok=True)
                    combined.to_csv(MEAL_DATA_PATH, index=False)
                    st.success("✅ Meal saved!")
                    # commit to GitHub
                    commit_file_to_github(
                        MEAL_DATA_PATH, "data/meals.csv", "Update meals"
                    )
                    # Reset builder state but keep saved meals visible
                    st.session_state.meal_name = ""
                    st.session_state.meal_ingredients = pd.DataFrame(
                        columns=[
                            "Ingredient",
                            "Quantity",
                            "Cost per Unit",
                            "Total Cost",
                            "Input Unit",
                        ]
                    )
                    st.session_state.new_meal_qty = 0.0
                    st.session_state.new_meal_unit = None
                except Exception as e:
                    st.error(f"Failed to save meal: {e}")

    st.markdown("---")
    # ----------------------
    # List of saved meals
    # ----------------------
    st.subheader("📦 Saved Meals")
    if not meals_df.empty:
        unique_meals = sorted(meals_df["Meal"].dropna().unique())
        for meal in unique_meals:
            row_cols = st.columns([6, 1])
            row_cols[0].markdown(f"**{meal}**")
            if row_cols[1].button("Edit", key=f"edit_{meal}"):
                st.session_state.editing_meal = meal
        st.write("")  # spacing
    else:
        st.write("No saved meals yet.")

    # ----------------------
    # Edit existing meal
    # ----------------------
    if "editing_meal" in st.session_state and st.session_state.editing_meal:
        meal_name = st.session_state.editing_meal
        # Load a working copy in session_state
        edit_key = f"edit_{meal_name}_df"
        if edit_key not in st.session_state:
            df_to_edit = meals_df[meals_df["Meal"] == meal_name].copy()
            st.session_state[edit_key] = df_to_edit.reset_index(drop=True)
        editing_df = st.session_state[edit_key]

        # Modal if available
        context = None
        try:
            context = st.modal(f"Edit Meal: {meal_name}", key=f"modal_{meal_name}")
        except Exception:
            context = st.expander(f"Edit Meal: {meal_name}", expanded=True)

        with context:
            col1, col2 = st.columns([4, 2])
            with col1:
                new_name = st.text_input("Meal Name", value=meal_name, key=f"rename_{meal_name}")
            with col2:
                if st.button("🗑️ Delete Meal", key=f"delete_{meal_name}"):
                    # Remove all rows of this meal
                    updated = meals_df[meals_df["Meal"] != meal_name].copy()
                    updated.to_csv(MEAL_DATA_PATH, index=False)
                    commit_file_to_github(
                        MEAL_DATA_PATH, "data/meals.csv", "Delete meal"
                    )
                    st.success(f"Deleted meal '{meal_name}'.")
                    # Clean up edit state
                    del st.session_state[edit_key]
                    del st.session_state["editing_meal"]
                    return  # exit editing

            # Ingredient editing
            st.markdown("### Ingredients")
            new_rows = []
            remove_indices = []

            for idx in list(editing_df.index):
                row = editing_df.loc[idx]
                ingredient = row["Ingredient"]
                base_qty = float(row.get("Quantity", 0))
                cost_per_unit = float(row.get("Cost per Unit", 0))
                input_unit_original = row.get("Input Unit", None)

                # Determine base unit type
                info = ingredients_df[
                    ingredients_df["Ingredient"].str.lower() == str(ingredient).strip().lower()
                ]
                if not info.empty:
                    base_unit_type = info.iloc[0].get("Unit Type", "")
                else:
                    base_unit_type = ""

                # Convert base quantity to display
                display_qty, display_unit = base_to_display(base_qty, base_unit_type)
                # If original input unit exists, prefer showing that
                if input_unit_original:
                    display_unit = input_unit_original

                # Build row UI
                c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 1])
                with c1:
                    st.markdown(f"**{ingredient}**")
                with c2:
                    updated_qty = st.number_input(
                        f"Qty_{meal_name}_{idx}",
                        min_value=0.0,
                        step=0.1,
                        value=float(display_qty),
                        key=f"qty_{meal_name}_{idx}",
                        label_visibility="collapsed",
                    )
                with c3:
                    unit_options = get_display_unit_options(base_unit_type)
                    updated_unit = st.selectbox(
                        f"Unit_{meal_name}_{idx}",
                        options=unit_options,
                        index=unit_options.index(display_unit)
                        if display_unit in unit_options
                        else 0,
                        key=f"unit_{meal_name}_{idx}",
                        label_visibility="collapsed",
                    )
                with c4:
                    # Recompute base quantity & cost
                    qty_base_new = display_to_base(updated_qty, updated_unit, base_unit_type)
                    total_cost = round(qty_base_new * cost_per_unit, 6)
                    st.markdown(f"Cost: ${total_cost:.4f}")
                with c5:
                    if st.button("Remove", key=f"remove_{meal_name}_{idx}"):
                        remove_indices.append(idx)
                        st.info(f"Marked {ingredient} for removal.")

                # Update working row
                new_rows.append(
                    {
                        "Ingredient": ingredient,
                        "Quantity": qty_base_new,
                        "Cost per Unit": cost_per_unit,
                        "Total Cost": total_cost,
                        "Input Unit": updated_unit,
                    }
                )

            # Add new ingredient to existing meal
            st.markdown("#### Add new ingredient to this meal")
            add_col1, add_col2, add_col3, add_col4 = st.columns([3, 2, 2, 1])
            with add_col1:
                add_ingredient = st.selectbox(
                    "Ingredient to add",
                    options=ingredient_options,
                    key=f"add_ing_select_{meal_name}",
                )
            with add_col2:
                info = ingredients_df[
                    ingredients_df["Ingredient"].str.lower() == str(add_ingredient).strip().lower()
                ]
                base_unit = info.iloc[0].get("Unit Type", "") if not info.empty else ""
                add_qty = st.number_input(
                    f"Add Qty_{meal_name}",
                    min_value=0.0,
                    step=0.1,
                    key=f"add_qty_{meal_name}",
                    label_visibility="collapsed",
                )
            with add_col3:
                add_unit_opts = get_display_unit_options(base_unit)
                add_unit = st.selectbox(
                    f"Add Unit_{meal_name}",
                    options=add_unit_opts,
                    key=f"add_unit_{meal_name}",
                    label_visibility="collapsed",
                )
            with add_col4:
                if st.button("Add Ingredient", key=f"add_to_meal_{meal_name}"):
                    if add_qty <= 0:
                        st.warning("Quantity must be >0 to add.")
                    else:
                        # lookup details
                        match = ingredients_df[
                            ingredients_df["Ingredient"].str.lower()
                            == str(add_ingredient).strip().lower()
                        ]
                        if match.empty:
                            st.error(f"Ingredient '{add_ingredient}' not found.")
                        else:
                            row = match.iloc[0]
                            base_unit_type = row.get("Unit Type", "")
                            cpu = float(row.get("Cost Per Unit", 0.0))
                            qty_base_new = display_to_base(add_qty, add_unit, base_unit_type)
                            total_cost = round(qty_base_new * cpu, 6)
                            new_rows.append(
                                {
                                    "Ingredient": add_ingredient,
                                    "Quantity": qty_base_new,
                                    "Cost per Unit": cpu,
                                    "Total Cost": total_cost,
                                    "Input Unit": add_unit,
                                }
                            )
                            st.success(f"Added {add_qty}{add_unit} of {add_ingredient}.")

            # Save edits
            if st.button("💾 Save Changes", key=f"save_edit_{meal_name}"):
                final_meal_name = new_name.strip() if new_name.strip() else meal_name
                if final_meal_name != meal_name:
                    # renaming: ensure we don't collide
                    existing = meals_df[meals_df["Meal"] == final_meal_name]
                    if not existing.empty and final_meal_name != meal_name:
                        st.warning(f"A meal named '{final_meal_name}' already exists. Choose a different name.")
                        # fallback to original
                        final_meal_name = meal_name

                # Reconstruct updated ingredient rows, excluding removals
                updated_rows = pd.DataFrame(new_rows)
                if updated_rows.empty:
                    st.warning("Meal must have at least one ingredient. Aborting save.")
                else:
                    # Drop original meal rows
                    cleaned = meals_df[meals_df["Meal"] != meal_name].copy()
                    # Insert updated with new meal name
                    updated_rows.insert(0, "Meal", final_meal_name)
                    combined = pd.concat([cleaned, updated_rows], ignore_index=True)
                    try:
                        os.makedirs("data", exist_ok=True)
                        combined.to_csv(MEAL_DATA_PATH, index=False)
                        st.success(f"✅ Meal '{final_meal_name}' updated.")
                        commit_file_to_github(
                            MEAL_DATA_PATH, "data/meals.csv", "Update meals"
                        )
                        # Clean up editing state
                        if final_meal_name != meal_name:
                            # rename stored edit key
                            del st.session_state[f"edit_{meal_name}_df"]
                            st.session_state.editing_meal = final_meal_name
                        else:
                            del st.session_state[f"edit_{meal_name}_df"]
                            del st.session_state["editing_meal"]
                    except Exception as e:
                        st.error(f"Failed to save edited meal: {e}")
