import pandas as pd
import os
import glob

# 1. Define your source files
# You can list them manually, or use glob to find them all
files = [
    "training_data_normal_market.parquet",
    "training_data_stressed_market.parquet", 
    "training_data_hft_dominated.parquet",
    "training_data_flash_crash.parquet",
    "training_data_mini_flash_crash.parquet"
]

# Alternative: Find all parquet files in the current directory
# files = glob.glob("training_data_*.parquet")

combined_frames = []

print(f"Found {len(files)} files to process...")

for file_path in files:
    if not os.path.exists(file_path):
        print(f"Skipping {file_path} (not found)")
        continue
        
    print(f"Processing {file_path}...")
    
    # Read the file
    df = pd.read_parquet(file_path)
    
    # Extract scenario name from filename if needed, or map it manually
    # Assuming filename format: "training_data_{SCENARIO}.parquet"
    # or just using the filename as the ID
    scenario_name = file_path.replace("training_data_", "").replace(".parquet", "")
    
    # Add/Overwrite the 'scenario' column
    df['scenario'] = scenario_name
    
    combined_frames.append(df)

# Combine all into one master DataFrame
if combined_frames:
    master_df = pd.concat(combined_frames, ignore_index=True)
    
    # Save the combined file
    output_filename = "master_training_data.parquet"
    master_df.to_parquet(output_filename)
    
    print(f"\nSUCCESS!")
    print(f"Combined {len(combined_frames)} files into '{output_filename}'")
    print(f"Total rows: {len(master_df)}")
    print(f"Scenarios included: {master_df['scenario'].unique()}")
    
    # Optional: Preview data
    print("\nData Preview:")
    print(master_df.head())
else:
    print("\nNo files were processed.")
