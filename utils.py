# utils.py

import os
import pandas as pd

def save_ingredients(df: pd.DataFrame):
    df.to_csv("data/ingredients.csv", index=False)
