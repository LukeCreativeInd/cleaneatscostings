import streamlit as st
import pandas as pd
import os
import requests
import base64
import uuid
from datetime import datetime

MEAL_DATA_PATH = "data/meals.csv"
INGREDIENTS_PATH = "data/ingredients.csv"

# Utility functions

def display_to_base(qty, display_unit, base_unit_type):
    t = (base_unit_type or "").upper()
    u = (display_unit or "").lower()
    if t == "KG": return qty/1000.0 if u in ["g","gram","grams"] else qty
    if t == "L": return qty/1000.0 if u=="ml" else qty
    return qty


def base_to_display(qty, base_unit_type):
    t = (base_unit_type or "").upper()
    if t == "KG": return (qty*1000.0, "g") if qty<1 else (qty, "kg")
    if t == "L": return (qty*1000.0, "ml") if qty<1 else (qty, "L")
    return (qty, "unit")


def get_display_unit_options(base_unit_type):
    t = (base_unit_type or "").upper()
    if t=="KG": return ["kg","g"]
    if t=="L": return ["L","ml"]
    return ["unit"]

# Data loaders

def load_meals():
    if os.path.exists(MEAL_DATA_PATH):
        df=pd.read_csv(MEAL_DATA_PATH)
        df.columns=df.columns.str.strip()
        if "Sell Price" not in df.columns: df["Sell Price"]=0.0
        return df
    return pd.DataFrame(columns=["Meal","Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit","Sell Price"])


def load_ingredients():
    if os.path.exists(INGREDIENTS_PATH):
        df=pd.read_csv(INGREDIENTS_PATH)
        df.columns=df.columns.str.strip().str.title()
        if "Cost Per Unit" not in df.columns:
            df["Cost Per Unit"]=df.apply(
                lambda r: round(float(r["Cost"])/float(r["Purchase Size"]),6) if float(r["Purchase Size"]) else 0,
                axis=1)
        df["Ingredient"]=df["Ingredient"].astype(str).str.strip().str.title()
        df["Unit Type"]=df.get("Unit Type","unit").astype(str).str.strip().str.upper()
        return df
    return pd.DataFrame(columns=["Ingredient","Unit Type","Purchase Size","Cost","Cost Per Unit"])

# GitHub helper

def commit_file_to_github(local_path, repo_path, msg):
    try:
        token=st.secrets["github_token"]
        repo=st.secrets["github_repo"]
        branch=st.secrets.get("github_branch","main")
    except: return
    url=f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json"}
    with open(local_path,"rb") as f:
        content=base64.b64encode(f.read()).decode()
    resp=requests.get(url,headers=headers,params={"ref":branch})
    sha=resp.json().get("sha") if resp.status_code==200 else None
    payload={"message":f"{msg} {datetime.utcnow().isoformat()}Z","content":content,"branch":branch}
    if sha: payload["sha"]=sha
    put=requests.put(url,headers=headers,json=payload)
    if put.status_code not in (200,201): st.error(f"GitHub commit failed: {put.status_code}")

# Callbacks

def add_temp():
    ing_df=load_ingredients()
    sel=st.session_state["new_ing"]
    row=ing_df[ing_df["Ingredient"]==sel].iloc[0]
    qty=st.session_state["new_qty"]
    bq=display_to_base(qty,st.session_state["new_unit"],row["Unit Type"])
    cpu=float(row["Cost Per Unit"])
    total=round(bq*cpu,6)
    entry={"Ingredient":sel,"Quantity":bq,"Cost per Unit":cpu,"Total Cost":total,"Input Unit":st.session_state["new_unit"]}
    st.session_state["meal_ingredients"]=pd.concat([st.session_state["meal_ingredients"],pd.DataFrame([entry])],ignore_index=True)


def save_new_meal():
    mdf=load_meals()
    temp=st.session_state["meal_ingredients"].copy()
    temp["Meal"]=st.session_state["meal_name"].strip()
    temp["Sell Price"]=st.session_state["meal_sell_price"]
    out=pd.concat([mdf,temp],ignore_index=True)
    os.makedirs(os.path.dirname(MEAL_DATA_PATH),exist_ok=True)
    out.to_csv(MEAL_DATA_PATH,index=False)
    commit_file_to_github(MEAL_DATA_PATH,"data/meals.csv","Update meals")
    st.success("✅ Meal saved!")
    st.session_state["meal_ingredients"]=pd.DataFrame(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"])
    st.session_state["meal_form_key"]=str(uuid.uuid4())

# Main UI

def render():
    st.header("🍽️ Meal Builder")
    st.info("Build meals by adding ingredients & set a sell price; then save and edit meals.")

    meals_df=load_meals()
    ing_df=load_ingredients()
    opts=sorted(ing_df["Ingredient"].unique())

    st.session_state.setdefault("meal_name","")
    st.session_state.setdefault("meal_sell_price",0.0)
    st.session_state.setdefault("meal_ingredients",pd.DataFrame(columns=["Ingredient","Quantity","Cost per Unit","Total Cost","Input Unit"]))
    st.session_state.setdefault("meal_form_key",str(uuid.uuid4()))
    st.session_state.setdefault("editing_meal",None)

    with st.form(key=st.session_state["meal_form_key"]):
        c1,c2=st.columns([3,2])
        c1.text_input("Meal Name",key="meal_name")
        c2.number_input("Sell Price",min_value=0.0,step=0.01,key="meal_sell_price")

        d1,d2,d3,d4=st.columns([3,2,2,1])
        d1.selectbox("Ingredient",opts,key="new_ing")
        d2.number_input("Qty/Amt",min_value=0.0,step=0.1,key="new_qty")
        base=ing_df[ing_df["Ingredient"]==st.session_state["new_ing"]]
        uopts=get_display_unit_options(base.iloc[0]["Unit Type"]) if not base.empty else ["unit"]
        d3.selectbox("Unit",uopts,key="new_unit")
        if d4.form_submit_button("➕ Add Ingredient"):
            if not st.session_state["meal_name"].strip(): st.warning("Enter a meal name first.")
            elif st.session_state["new_qty"]<=0: st.warning("Quantity must be >0.")
            else: add_temp()

        if st.form_submit_button("💾 Save Meal"):
            if st.session_state["meal_ingredients"].empty: st.warning("Add at least one ingredient.")
            else: save_new_meal()

    if not st.session_state["meal_ingredients"].empty:
        st.subheader(f"🧾 Ingredients for '{st.session_state['meal_name']}' (unsaved)")
        df=st.session_state["meal_ingredients"].copy()
        df["Display"]=df.apply(lambda r:f"{base_to_display(r['Quantity'],r['Input Unit'])[0]:.2f} {r['Input Unit']}",axis=1)
        st.dataframe(df[["Ingredient","Display","Cost per Unit","Total Cost"]],use_container_width=True)

    st.markdown("---")
    st.subheader("📦 Saved Meals")
    for mn in meals_df['Meal'].unique():
        key=f"btn_{mn}"
        if st.session_state['editing_meal']!=mn:
            if st.button(f"✏️ {mn}",key=key):
                st.session_state['editing_meal']=mn
                st.session_state[f'edit_{mn}']=meals_df[meals_df['Meal']==mn].reset_index(drop=True)
        else:
            df_edit=st.session_state[f'edit_{mn}']
            exp=st.expander(f"Edit Meal {mn}",expanded=True)
            with exp:
                nm=st.text_input("Meal Name",value=mn,key=f"rename_{mn}")
                pr=st.number_input("Sell Price",min_value=0.0,step=0.01,value=float(meals_df.loc[meals_df['Meal']==mn,'Sell Price'].iloc[0]),key=f"sellprice_{mn}")
                if st.button("🗑️ Delete Meal",key=f"del_{mn}"):
                    rem=meals_df[meals_df['Meal']!=mn]
                    rem.to_csv(MEAL_DATA_PATH,index=False)
                    commit_file_to_github(MEAL_DATA_PATH,"data/meals.csv","Delete meal")
                    st.success(f"Deleted {mn}")
                    del st.session_state[f'edit_{mn}']
                    st.session_state['editing_meal']=None
                    break
                st.markdown("### Ingredients")
                for i,r in df_edit.iterrows():
                    cols=st.columns([3,2,2,1,1])
                    cols[0].write(r['Ingredient'])
                    q=cols[1].number_input("Qty",value=base_to_display(r['Quantity'],r['Input Unit'])[0],min_value=0.0,step=0.1,key=f"qty_{mn}_{i}")
                    usel=cols[2].selectbox("Unit",get_display_unit_options(r['Input Unit']),index=get_display_unit_options(r['Input Unit']).index(r['Input Unit']),key=f"unit_{mn}_{i}")
                    bq2=display_to_base(q,usel,r['Input Unit'])
                    tot=round(bq2*float(r['Cost per Unit']),6)
                    cols[3].write(f"Cost: ${tot}")
                    if cols[4].button("Remove",key=f"rem_{mn}_{i}"):
                        df_edit=df_edit.drop(i).reset_index(drop=True)
                        st.session_state[f'edit_{mn}']=df_edit
                        break
                st.markdown("### Add Ingredient")
                a1,a2,a3,a4=st.columns([3,2,2,1])
                ni=a1.selectbox("Ingredient",opts,key=f"new_ing_{mn}")
                nq=a2.number_input("Qty",min_value=0.0,step=0.1,key=f"new_qty_{mn}")
                bu=ing_df[ing_df['Ingredient']==ni]
                uo=get_display_unit_options(bu.iloc[0]['Unit Type']) if not bu.empty else ['unit']
                nu=a3.selectbox("Unit",uo,key=f"new_unit_{mn}")
                if a4.button("➕ Add",key=f"add_{mn}"):
                    row=ing_df[ing_df['Ingredient']==ni].iloc[0]
                    bq3=display_to_base(nq,nu,row['Unit Type'])
                    tot3=round(bq3*float(row['Cost Per Unit']),6)
                    newrow={'Ingredient':ni,'Quantity':bq3,'Cost per Unit':float(row['Cost Per Unit']),'Total Cost':tot3,'Input Unit':nu}
                    df_edit=pd.concat([df_edit,pd.DataFrame([newrow])],ignore_index=True)
                    st.session_state[f'edit_{mn}']=df_edit
                    break
                if st.button("💾 Save Changes",key=f"sv_{mn}"):
                    df_edit['Meal']=nm.strip() or mn
                    df_edit['Sell Price']=pr
                    others=meals_df[meals_df['Meal']!=mn]
                    out=pd.concat([others,df_edit],ignore_index=True)
                    out.to_csv(MEAL_DATA_PATH,index=False)
                    commit_file_to_github(MEAL_DATA_PATH,"data/meals.csv","Save edited meal")
                    st.success(f"✅ Saved {df_edit['Meal'].iloc[0]}")
                    del st.session_state[f'edit_{mn}']
                    st.session_state['editing_meal']=None
