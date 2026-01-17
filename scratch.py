import pandas as pd

df = pd.read_parquet("training_data_normal_market_20260117_145833.parquet")

df.show(limit=None)
