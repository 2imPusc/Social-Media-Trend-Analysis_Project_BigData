import pandas as pd
import glob
import os

DATA_DIR = "Data"
OUTPUT_DIR = "Data/merged"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def merge_csv_files(data_type):
    files = glob.glob(os.path.join(DATA_DIR, f"{data_type}_*.csv"))
    if not files:
        print(f"No {data_type} files found")
        return
    dfs = [pd.read_csv(file) for file in files]
    merged_df = pd.concat(dfs, ignore_index=True)
    output_file = os.path.join(OUTPUT_DIR, f"{data_type}.csv")
    merged_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"Merged {len(dfs)} files into {output_file}")

merge_csv_files("contents")
merge_csv_files("comments")
merge_csv_files("captions")