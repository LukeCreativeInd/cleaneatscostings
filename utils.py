import os
import pandas as pd

def save_ingredients(df: pd.DataFrame):
    os.makedirs("data", exist_ok=True)  # ✅ ensures folder exists
    df.to_csv("data/ingredients.csv", index=False)
