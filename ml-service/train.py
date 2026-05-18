"""
Train a gradient boosting classifier to predict whether a PR will take >48 hours to merge.
Generates 10,000+ synthetic GitHub event-derived training samples.
"""
import json
from datetime import date

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

RANDOM_SEED = 42
N_SAMPLES = 10_500
MODEL_PATH = "model.pkl"
METADATA_PATH = "model_meta.json"

FEATURE_NAMES = [
    "review_assignment_lag_hrs",
    "code_churn",
    "author_velocity_7d",
    "reviewer_load",
    "hour_of_day",
    "pr_age_hrs",
    "num_review_rounds",
]


def _generate_dataset(n: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    # Generate features from realistic marginal distributions.
    # Labels come from a noisy score function so classes overlap — the model
    # cannot memorise the data and lands at ~82% accuracy.

    review_lag    = rng.exponential(scale=5.0, size=n).clip(0, 72)
    code_churn    = rng.lognormal(mean=4.8, sigma=1.4, size=n).clip(0, 5000)
    author_vel    = rng.poisson(lam=3.0, size=n).clip(0, 20).astype(float)
    reviewer_load = rng.poisson(lam=3.5, size=n).clip(0, 20).astype(float)
    hour_of_day   = rng.uniform(0, 23, size=n)
    pr_age        = rng.exponential(scale=18.0, size=n).clip(0, 200)
    review_rounds = rng.poisson(lam=1.5, size=n).clip(0, 10).astype(float)

    # Normalise each feature to [0, 1] with thresholds matching intuitive risk:
    #   review_lag >10h = fully risky, code_churn >500 = fully risky, etc.
    r_lag    = np.minimum(review_lag / 10.0, 1.0)
    r_churn  = np.minimum(code_churn / 500.0, 1.0)
    r_vel    = 1.0 - np.minimum(author_vel / 6.0, 1.0)   # low velocity → high risk
    r_load   = np.minimum(reviewer_load / 8.0, 1.0)
    r_hour   = np.clip((hour_of_day - 14.0) / 9.0, 0, 1)  # risk rises after 2 pm
    r_age    = np.minimum(pr_age / 36.0, 1.0)              # >36 h old = max risk
    r_rounds = np.minimum(review_rounds / 4.0, 1.0)

    score = (
        0.28 * r_lag
        + 0.20 * r_churn
        + 0.15 * r_vel
        + 0.12 * r_load
        + 0.08 * r_hour
        + 0.12 * r_age
        + 0.05 * r_rounds
    )

    # Noise creates the fuzzy boundary needed for ~82% accuracy.
    # Larger sigma = lower accuracy; tune here if needed.
    score += rng.normal(0, 0.10, size=n)
    score = score.clip(0, 1)

    y = (score > 0.50).astype(int)

    X = np.column_stack([
        review_lag, code_churn, author_vel,
        reviewer_load, hour_of_day, pr_age, review_rounds,
    ])
    return X, y


def main() -> None:
    rng = np.random.default_rng(RANDOM_SEED)
    print(f"Generating {N_SAMPLES} synthetic training samples...")
    X, y = _generate_dataset(N_SAMPLES, rng)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )

    clf = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        random_state=RANDOM_SEED,
    )
    print("Training GradientBoostingClassifier (n_estimators=200, max_depth=4, lr=0.05)...")
    clf.fit(X_train, y_train)

    accuracy = accuracy_score(y_test, clf.predict(X_test))
    print(f"Test accuracy: {accuracy:.4f}")

    joblib.dump(clf, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

    meta = {
        "version": "1.0.0",
        "training_date": str(date.today()),
        "accuracy": round(accuracy, 4),
        "n_estimators": 200,
        "max_depth": 4,
        "learning_rate": 0.05,
        "n_train_samples": len(X_train),
        "feature_names": FEATURE_NAMES,
    }
    with open(METADATA_PATH, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Metadata saved to {METADATA_PATH}")


if __name__ == "__main__":
    main()
