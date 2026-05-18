"""
Metric computation against the PostgreSQL aggregation store.
All queries use SQLAlchemy 2.0 async style.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Event, PullRequest, ReviewRequest


async def get_pr_metrics(session: AsyncSession, pr_id: int) -> dict[str, Any] | None:
    pr = await session.get(PullRequest, pr_id)
    if pr is None:
        return None

    review_requests = (
        await session.execute(
            select(ReviewRequest).where(ReviewRequest.pr_id == pr_id)
        )
    ).scalars().all()

    review_assignment_lag_hrs: float | None = None
    if pr.first_reviewer_assigned_at and pr.created_at:
        delta = pr.first_reviewer_assigned_at - pr.created_at
        review_assignment_lag_hrs = round(delta.total_seconds() / 3600, 2)

    merge_time_hrs: float | None = None
    if pr.merged_at and pr.created_at:
        delta = pr.merged_at - pr.created_at
        merge_time_hrs = round(delta.total_seconds() / 3600, 2)

    pr_age_hrs = round(
        (datetime.now(timezone.utc) - pr.created_at).total_seconds() / 3600, 2
    )

    return {
        "pr_id": pr.id,
        "pr_number": pr.pr_number,
        "repo": pr.repo,
        "author": pr.author,
        "title": pr.title,
        "state": pr.state,
        "created_at": pr.created_at.isoformat(),
        "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
        "code_churn": pr.additions + pr.deletions,
        "additions": pr.additions,
        "deletions": pr.deletions,
        "changed_files": pr.changed_files,
        "review_rounds": pr.review_rounds,
        "review_assignment_lag_hrs": review_assignment_lag_hrs,
        "merge_time_hrs": merge_time_hrs,
        "pr_age_hrs": pr_age_hrs,
        "reviewers": [
            {
                "reviewer": rr.reviewer,
                "assigned_at": rr.assigned_at.isoformat(),
                "reviewed_at": rr.reviewed_at.isoformat() if rr.reviewed_at else None,
                "state": rr.review_state,
            }
            for rr in review_requests
        ],
    }


async def get_author_metrics(session: AsyncSession, author: str) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    prs_opened_7d = (
        await session.execute(
            select(func.count()).where(
                PullRequest.author == author,
                PullRequest.created_at >= cutoff,
            )
        )
    ).scalar_one()

    prs_merged_7d = (
        await session.execute(
            select(func.count()).where(
                PullRequest.author == author,
                PullRequest.merged_at >= cutoff,
            )
        )
    ).scalar_one()

    open_prs_rows = (
        await session.execute(
            select(PullRequest).where(
                PullRequest.author == author,
                PullRequest.state == "open",
            )
        )
    ).scalars().all()

    # Average review lag across closed PRs by this author
    closed_with_lag = (
        await session.execute(
            select(PullRequest).where(
                PullRequest.author == author,
                PullRequest.first_reviewer_assigned_at.is_not(None),
            )
        )
    ).scalars().all()

    avg_review_lag: float | None = None
    if closed_with_lag:
        lags = [
            (pr.first_reviewer_assigned_at - pr.created_at).total_seconds() / 3600
            for pr in closed_with_lag
            if pr.first_reviewer_assigned_at
        ]
        avg_review_lag = round(sum(lags) / len(lags), 2) if lags else None

    return {
        "author": author,
        "prs_opened_7d": prs_opened_7d,
        "prs_merged_7d": prs_merged_7d,
        "avg_review_lag_hrs": avg_review_lag,
        "open_prs": [
            {"pr_id": pr.id, "pr_number": pr.pr_number, "title": pr.title, "repo": pr.repo}
            for pr in open_prs_rows
        ],
    }


async def get_repo_metrics(session: AsyncSession, repo: str) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    open_pr_count = (
        await session.execute(
            select(func.count()).where(
                PullRequest.repo == repo,
                PullRequest.state == "open",
            )
        )
    ).scalar_one()

    throughput_7d = (
        await session.execute(
            select(func.count()).where(
                PullRequest.repo == repo,
                PullRequest.merged_at >= cutoff,
            )
        )
    ).scalar_one()

    merged_prs = (
        await session.execute(
            select(PullRequest).where(
                PullRequest.repo == repo,
                PullRequest.merged_at.is_not(None),
            )
        )
    ).scalars().all()

    avg_merge_time_hrs: float | None = None
    if merged_prs:
        times = [
            (pr.merged_at - pr.created_at).total_seconds() / 3600
            for pr in merged_prs
            if pr.merged_at
        ]
        avg_merge_time_hrs = round(sum(times) / len(times), 2) if times else None

    return {
        "repo": repo,
        "open_pr_count": open_pr_count,
        "throughput_7d": throughput_7d,
        "avg_merge_time_hrs": avg_merge_time_hrs,
    }


async def upsert_pull_request(session: AsyncSession, event: dict[str, Any]) -> None:
    pr_id = event.get("pr_id")
    if not pr_id:
        return

    existing = await session.get(PullRequest, pr_id)
    action = event.get("action", "")

    def _parse_dt(val: str | None) -> datetime | None:
        if not val:
            return None
        return datetime.fromisoformat(val.replace("Z", "+00:00"))

    if existing is None:
        pr = PullRequest(
            id=pr_id,
            pr_number=event.get("pr_number", 0),
            repo=event.get("repo", ""),
            author=event.get("author", ""),
            title=event.get("pr_title", ""),
            state=event.get("state", "open"),
            created_at=_parse_dt(event.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_parse_dt(event.get("updated_at")) or datetime.now(timezone.utc),
            merged_at=_parse_dt(event.get("merged_at")),
            closed_at=_parse_dt(event.get("closed_at")),
            additions=event.get("additions", 0),
            deletions=event.get("deletions", 0),
            changed_files=event.get("changed_files", 0),
            head_sha=event.get("head_sha"),
            base_branch=event.get("base_branch"),
        )
        session.add(pr)
    else:
        existing.state = event.get("state", existing.state)
        existing.updated_at = _parse_dt(event.get("updated_at")) or existing.updated_at
        existing.merged_at = _parse_dt(event.get("merged_at")) or existing.merged_at
        existing.closed_at = _parse_dt(event.get("closed_at")) or existing.closed_at
        existing.additions = event.get("additions", existing.additions)
        existing.deletions = event.get("deletions", existing.deletions)
        if action in ("review_requested",):
            existing.review_rounds += 1

    # Track reviewer assignments
    if action == "review_requested":
        for reviewer_login in event.get("requested_reviewers", []):
            now = datetime.now(timezone.utc)
            rr = ReviewRequest(
                pr_id=pr_id,
                reviewer=reviewer_login,
                assigned_at=now,
            )
            session.add(rr)
            # Update first_reviewer_assigned_at on the PR
            pr_obj = existing or pr
            if pr_obj.first_reviewer_assigned_at is None:
                pr_obj.first_reviewer_assigned_at = now

    await session.commit()


async def upsert_review(session: AsyncSession, event: dict[str, Any]) -> None:
    pr_id = event.get("pr_id")
    reviewer = event.get("reviewer")
    if not pr_id or not reviewer:
        return

    result = await session.execute(
        select(ReviewRequest).where(
            ReviewRequest.pr_id == pr_id,
            ReviewRequest.reviewer == reviewer,
            ReviewRequest.reviewed_at.is_(None),
        )
    )
    rr = result.scalars().first()
    if rr:
        rr.reviewed_at = datetime.now(timezone.utc)
        rr.review_state = event.get("review_state")

    # Increment review rounds on the PR
    pr = await session.get(PullRequest, pr_id)
    if pr:
        pr.review_rounds += 1

    await session.commit()


async def get_open_prs(
    session: AsyncSession, repo: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    q = select(PullRequest).where(PullRequest.state == "open")
    if repo:
        q = q.where(PullRequest.repo == repo)
    q = q.order_by(PullRequest.created_at.asc()).limit(limit)
    prs = (await session.execute(q)).scalars().all()

    result = []
    for pr in prs:
        pr_age_hrs = round(
            (datetime.now(timezone.utc) - pr.created_at).total_seconds() / 3600, 2
        )
        review_lag_hrs: float | None = None
        if pr.first_reviewer_assigned_at:
            review_lag_hrs = round(
                (pr.first_reviewer_assigned_at - pr.created_at).total_seconds() / 3600, 2
            )
        result.append({
            "pr_id": pr.id,
            "pr_number": pr.pr_number,
            "repo": pr.repo,
            "author": pr.author,
            "title": pr.title,
            "created_at": pr.created_at.isoformat(),
            "pr_age_hrs": pr_age_hrs,
            "code_churn": pr.additions + pr.deletions,
            "review_rounds": pr.review_rounds,
            "review_assignment_lag_hrs": review_lag_hrs,
        })
    return result


async def persist_event(session: AsyncSession, event: dict[str, Any]) -> None:
    db_event = Event(
        event_id=event["event_id"],
        event_type=event["event_type"],
        repo=event.get("repo", ""),
        ingested_at=datetime.now(timezone.utc),
        payload=json.dumps(event),
    )
    session.add(db_event)
    await session.commit()
