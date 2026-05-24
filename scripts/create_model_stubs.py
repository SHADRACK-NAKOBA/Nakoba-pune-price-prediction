"""Create minimal but valid model stub files for CI smoke testing.

Generates the same 6 artifacts that src/inference.py loads at startup,
so the Docker container can start and /health can respond without real
trained model files. Never use these stubs in production.
"""
import os
import pickle

import joblib
import numpy as np
from sklearn.ensemble import VotingRegressor
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import Lasso, LinearRegression, Ridge

os.makedirs("model", exist_ok=True)

# VotingRegressor trained on a 115-feature dummy dataset
X = np.zeros((5, 115))
y = np.ones(5)
m = VotingRegressor(
    [("lr", LinearRegression()), ("ridge", Ridge()), ("lasso", Lasso())]
)
m.fit(X, y)
joblib.dump(m, "model/property_price_prediction_voting.sav")

# CountVectorizer with exactly 100 features
cv = CountVectorizer(max_features=100)
cv.fit([" ".join(f"word{i}" for i in range(100))])
with open("model/count_vectorizer.pkl", "wb") as f:
    pickle.dump(cv, f)

with open("model/interval_est.pkl", "wb") as f:
    pickle.dump({"z_score": 1.96, "residual_std": 16.0}, f)

with open("model/sub_area_price_map.pkl", "wb") as f:
    pickle.dump({}, f)

with open("model/amenities_score_price_map.pkl", "wb") as f:
    pickle.dump({}, f)

with open("model/all_feature_names.pkl", "wb") as f:
    pickle.dump([f"s{i}" for i in range(15)] + [f"t{i}" for i in range(100)], f)

print("Stub model artifacts created for CI smoke test.")
