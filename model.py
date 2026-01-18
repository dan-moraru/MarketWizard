import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# ==============================================================================
# 1. LOAD DATA
# ==============================================================================
print("Loading data...")
df = pd.read_parquet("master_training_data.parquet")

# Filter out "crash" scenarios as requested
df = df[~df["scenario"].str.contains("crash", case=False)].copy()

# ==============================================================================
# 2. FEATURE ENGINEERING (MULTI-SCALE)
# ==============================================================================
print("Generating Multi-Scale features...")

# We group by scenario so rolling windows don't bleed from one run to the next
grouped = df.groupby("scenario")

# --- Base Calculations ---
# Relative spread (Spread as a % of price)
df["spread_rel"] = (df["ask"] - df["bid"]) / df["mid"]

# Absolute price change per step (for velocity)
df["mid_change_abs"] = grouped["mid"].transform(lambda x: x.diff().abs())

# --- Multi-Scale Loop ---
# 20/50   = "Reflexes" (Microstructure)
# 200     = "Tactical" (Short Trends)
# 500/1000= "Strategic" (Market Regimes / Deep Lookback)
windows = [20, 50, 200, 500, 1000]

for w in windows:
    # 1. Volatility (Standard Deviation of price)
    df[f"vol_{w}"] = grouped["mid"].transform(lambda x: x.rolling(window=w).std())

    # 2. Velocity (EMA of absolute price changes)
    # Using EMA here because it reacts faster to recent changes than simple rolling mean
    df[f"velocity_ema_{w}"] = grouped["mid_change_abs"].transform(
        lambda x: x.ewm(span=w, adjust=False).mean()
    )

    # 3. Spread Context (Is current spread tight or wide relative to this window?)
    df[f"spread_ma_{w}"] = grouped["spread_rel"].transform(
        lambda x: x.rolling(window=w).mean()
    )
    # Normalize spread: > 1.0 means spread is wider than average for this window
    df[f"spread_norm_{w}"] = df["spread_rel"] / df[f"spread_ma_{w}"]

# --- Divergence Features (The "Why" of the lookback) ---
# These help the tree find contradictions (e.g., Volatility is low long-term, but spiking short-term)

# Volatility Shock: Short-term vol vs Long-term vol
df["vol_shock_20_1000"] = df["vol_20"] / df["vol_1000"]

# Velocity Acceleration: Is the market speeding up?
df["velocity_accel_20_500"] = df["velocity_ema_20"] / df["velocity_ema_500"]

# Trend Deviation: Distance from the long-term mean (1000 steps)
df["ma_1000"] = grouped["mid"].transform(lambda x: x.rolling(window=1000).mean())
df["trend_deviation"] = (df["mid"] - df["ma_1000"]) / df["mid"]

# --- Cleanup ---
# CRITICAL: This will drop the first 1000 rows of EVERY scenario due to the largest window.
# Ensure your scenarios are long enough (e.g., >2000 steps) for this to be viable.
print(f"Data shape before dropna: {df.shape}")
df = df.dropna().copy()
print(f"Data shape after dropna: {df.shape}")

# ==============================================================================
# 3. MODEL PREPARATION
# ==============================================================================

# Columns to drop (Raw identifiers and raw prices that shouldn't be features)
features_to_drop = [
    "scenario",
    "label",
    "timestamp",
    "step",
    "run_id",
    "bid",
    "ask",
    "mid",
    "spread",
    "mid_change_abs",  # Drop intermediate calculation
    "ma_1000",  # Drop raw moving average price (not normalized)
]

# Clean up list in case columns don't exist
existing_cols_to_drop = [c for c in features_to_drop if c in df.columns]

# Encode Labels
le = LabelEncoder()
df["label"] = le.fit_transform(df["scenario"])

# ==============================================================================
# 4. SPLITTING STRATEGY: CHRONOLOGICAL
# ==============================================================================
print("Splitting data chronologically per scenario...")

X_train_list = []
y_train_list = []
X_test_list = []
y_test_list = []

for scenario_name in df["scenario"].unique():
    # Get all rows for this scenario, preserving time order
    scenario_data = df[df["scenario"] == scenario_name]

    # Calculate split index (75% train, 25% test)
    split_idx = int(len(scenario_data) * 0.75)

    train_subset = scenario_data.iloc[:split_idx]
    test_subset = scenario_data.iloc[split_idx:]

    # Append to lists
    X_train_list.append(train_subset.drop(columns=existing_cols_to_drop + ["label"]))
    y_train_list.append(train_subset["label"])

    X_test_list.append(test_subset.drop(columns=existing_cols_to_drop + ["label"]))
    y_test_list.append(test_subset["label"])

# Recombine
X_train = pd.concat(X_train_list)
y_train = pd.concat(y_train_list)
X_test = pd.concat(X_test_list)
y_test = pd.concat(y_test_list)

print(f"Training on {len(X_train)} samples, Testing on {len(X_test)} samples.")
print(f"Feature count: {len(X_train.columns)}")

# ==============================================================================
# 5. MODEL TRAINING
# ==============================================================================
model = XGBClassifier(
    n_estimators=300,
    max_depth=6,  # Increased slightly to handle feature interactions
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="multi:softmax",
    num_class=len(le.classes_),
    n_jobs=-1,  # Use all CPU cores
)

print("Fitting model...")
model.fit(X_train, y_train)

# ==============================================================================
# 6. RESULTS & EVALUATION
# ==============================================================================
y_pred = model.predict(X_test)

print("\n" + "=" * 40)
print("Classification Report")
print("=" * 40)
print(classification_report(y_test, y_pred, target_names=le.classes_))

print("\nTop 15 Feature Importances:")
importances = pd.Series(model.feature_importances_, index=X_train.columns)
print(importances.sort_values(ascending=False).head(15))

# Save the model
model.save_model("market_classifier_multi_scale.pkl")
print("\nModel saved to market_classifier_multi_scale.pkl")
