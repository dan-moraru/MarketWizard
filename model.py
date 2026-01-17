import pandas as pd
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# Init
files = [
    "market_data_normal_market.csv",
    "market_data_stressed_market.csv",
    "market_data_flash_crash.csv",
    "market_data_mini_flash_crash.csv",
    "market_data_hft_dominated.csv"
]

df = pd.concat([pd.read_csv(f) for f in files])

# Scenarios to labels
le = LabelEncoder()
df["label"] = le.fit_transform(df["scenario"])

X = df.drop(columns=["scenario", "label"])
y = df["label"]

# XGBoost 
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
    num_class=5
)

model.fit(X_train, y_train)

y_pred = model.predict(X_test)

print(classification_report(y_test, y_pred, target_names=le.classes_))
