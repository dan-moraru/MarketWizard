import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# 1. Load Data
df = pd.read_parquet("master_training_data.parquet")

# 2. Filter out crashes (as you requested)
df = df[~df['scenario'].str.contains("crash", case=False)].copy()

# ==============================================================================
# FEATURE ENGINEERING
# ==============================================================================
print("Generating features...")

# We group by 'scenario' so rolling windows don't bleed between different runs
# e.g., The end of 'normal' shouldn't affect the start of 'stressed'
grouped = df.groupby('scenario')

# A. Spread Dynamics
# Relative spread is better than absolute (0.01 at price 10 is different than at price 1000)
df['spread_rel'] = (df['ask'] - df['bid']) / df['mid']

# B. Volatility (The most important feature)
# Standard deviation of mid-price over the last 20 and 50 ticks
df['vol_20'] = grouped['mid'].transform(lambda x: x.rolling(window=20).std())
df['vol_50'] = grouped['mid'].transform(lambda x: x.rolling(window=50).std())

# C. Momentum / Velocity
# Absolute change in mid price from previous tick
df['mid_change_abs'] = grouped['mid'].transform(lambda x: x.diff().abs())
# Exponential Moving Average of price changes (Recent speed)
df['velocity_ema'] = grouped['mid_change_abs'].transform(lambda x: x.ewm(span=20, adjust=False).mean())

# D. Spread Stability
# Is the spread widening? (Current spread vs 50-tick average)
df['spread_ma_50'] = grouped['spread_rel'].transform(lambda x: x.rolling(window=50).mean())
df['spread_ratio'] = df['spread_rel'] / df['spread_ma_50']

# 3. Clean up NaNs created by rolling windows
# (The first 50 rows of each scenario will be NaN)
df = df.dropna()

# ==============================================================================
# MODEL TRAINING
# ==============================================================================

# 4. Prepare X and y
# CRITICAL: Drop absolute identifiers and raw prices
features_to_drop = [
    "scenario", "label", "timestamp", "step", "run_id", 
    "bid", "ask", "mid", "spread" # Drop raw prices, keep derived features
]

# (Handle columns that might not exist if data_collector changed)
existing_cols_to_drop = [c for c in features_to_drop if c in df.columns]

le = LabelEncoder()
df["label"] = le.fit_transform(df["scenario"])

X = df.drop(columns=existing_cols_to_drop + ["label"]) # Drop target too
y = df["label"]

print(f"Training with features: {list(X.columns)}")

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)

model = XGBClassifier(
    n_estimators=300,
    max_depth=5,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="multi:softmax",
    num_class=len(le.classes_)
)

model.fit(X_train, y_train)

# ==============================================================================
# RESULTS
# ==============================================================================
y_pred = model.predict(X_test)

print("\n" + "="*40)
print("Classification Report")
print("="*40)
print(classification_report(y_test, y_pred, target_names=le.classes_))

print("\nFeature Importances:")
importances = pd.Series(model.feature_importances_, index=X.columns)
print(importances.sort_values(ascending=False))

# Optional: Save the model so your bot can load it
model.save_model("market_classifier.json")
print("\nModel saved to market_classifier.json")
