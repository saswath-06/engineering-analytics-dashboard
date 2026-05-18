"""
Feature extraction from PostgreSQL for production use.
Used by the scheduled retraining / batch prediction pipeline.
"""
from __future__ import annotations

import os
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:dev@localhost:5432/analytics")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def extract_pr_features(pr_id: int) -> dict[str, Any] | None:
    """Return the 7 model features for a given PR from the aggregation DB."""
    query = text("""
        SELECT
            pr.id,
            EXTRACT(EPOCH FROM (rr.first_assigned_at - pr.created_at)) / 3600.0
                AS review_assignment_lag_hrs,
            pr.additions + pr.deletions AS code_churn,
            COALESCE(av.prs_merged_7d, 0) AS author_velocity_7d,
            COALESCE(rl.open_requests, 0) AS reviewer_load,
            EXTRACT(HOUR FROM pr.created_at) AS hour_of_day,
            EXTRACT(EPOCH FROM (NOW() - pr.created_at)) / 3600.0 AS pr_age_hrs,
            COALESCE(pr.review_rounds, 0) AS num_review_rounds
        FROM pull_requests pr
        LEFT JOIN review_requests rr ON rr.pr_id = pr.id
        LEFT JOIN author_velocity av ON av.author = pr.author
        LEFT JOIN reviewer_load rl ON rl.reviewer = rr.first_reviewer
        WHERE pr.id = :pr_id
        LIMIT 1
    """)
    async with AsyncSessionLocal() as session:
        result = await session.execute(query, {"pr_id": pr_id})
        row = result.mappings().first()
        if row is None:
            return None
        return {
            "review_assignment_lag_hrs": float(row["review_assignment_lag_hrs"] or 0),
            "code_churn": int(row["code_churn"] or 0),
            "author_velocity_7d": int(row["author_velocity_7d"] or 0),
            "reviewer_load": int(row["reviewer_load"] or 0),
            "hour_of_day": int(row["hour_of_day"] or 0),
            "pr_age_hrs": float(row["pr_age_hrs"] or 0),
            "num_review_rounds": int(row["num_review_rounds"] or 0),
        }
