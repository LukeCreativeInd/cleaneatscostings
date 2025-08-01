import os
import pandas as pd
import subprocess

def save_ingredients_to_github(df: pd.DataFrame):
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    file_path = "data/ingredients.csv"

    # Save the DataFrame to CSV
    df.to_csv(file_path, index=False)

    # Stage, commit, and push the file using Git
    try:
        subprocess.run(["git", "add", file_path], check=True)
        subprocess.run(["git", "commit", "-m", "Update ingredients.csv from Streamlit"], check=True)
        subprocess.run(["git", "push"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")
        raise RuntimeError("Git push failed. Ensure the server has proper credentials configured.")
