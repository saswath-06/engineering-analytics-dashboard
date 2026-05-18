import json
import os
from pathlib import Path

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

MODEL_PATH = os.getenv("MODEL_PATH", "model.pkl")
METADATA_PATH = "model_meta.json"
PREDICTION_THRESHOLD = float(os.getenv("PREDICTION_THRESHOLD", "0.5"))

app = FastAPI(title="ML Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_clf = None
_meta: dict = {}


def _load_model():
    global _clf, _meta
    model_file = Path(MODEL_PATH)
    if not model_file.exists():
        raise RuntimeError(
            f"Model file '{MODEL_PATH}' not found. Run 'python train.py' first."
        )
    _clf = joblib.load(model_file)
    meta_file = Path(METADATA_PATH)
    if meta_file.exists():
        with open(meta_file) as f:
            _meta = json.load(f)


@app.on_event("startup")
async def startup():
    _load_model()


BUCKET_THRESHOLDS = [
    (0.25, "0-24h"),
    (0.50, "24-48h"),
    (1.01, "48h+"),
]


def _prob_to_bucket(prob: float) -> str:
    for threshold, label in BUCKET_THRESHOLDS:
        if prob < threshold:
            return label
    return "48h+"


class PRFeatures(BaseModel):
    review_assignment_lag_hrs: float = Field(..., ge=0, description="Hours from PR open to first reviewer assigned")
    code_churn: int = Field(..., ge=0, description="Total lines added + deleted")
    author_velocity_7d: int = Field(..., ge=0, description="PRs author merged in last 7 days")
    reviewer_load: int = Field(..., ge=0, description="Open review requests on assigned reviewer")
    hour_of_day: int = Field(..., ge=0, le=23, description="Hour PR was opened (0-23)")
    pr_age_hrs: float = Field(..., ge=0, description="Current PR age in hours")
    num_review_rounds: int = Field(..., ge=0, description="Number of review/revision cycles so far")


class PredictionResponse(BaseModel):
    at_risk: bool
    predicted_bucket: str
    confidence: float
    threshold_used: float


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ml", "model_loaded": _clf is not None}


@app.get("/model/info")
async def model_info():
    if not _meta:
        raise HTTPException(status_code=503, detail="Model metadata not available")
    return _meta


@app.post("/predict", response_model=PredictionResponse)
async def predict(features: PRFeatures):
    if _clf is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    X = np.array([[
        features.review_assignment_lag_hrs,
        features.code_churn,
        features.author_velocity_7d,
        features.reviewer_load,
        features.hour_of_day,
        features.pr_age_hrs,
        features.num_review_rounds,
    ]])

    prob = float(_clf.predict_proba(X)[0][1])
    at_risk = prob >= PREDICTION_THRESHOLD

    return PredictionResponse(
        at_risk=at_risk,
        predicted_bucket=_prob_to_bucket(prob),
        confidence=round(prob, 4),
        threshold_used=PREDICTION_THRESHOLD,
    )
