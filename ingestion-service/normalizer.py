from datetime import datetime, timezone
from typing import Any


def normalize_event(event_type: str, event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    base = {
        "event_id": event_id,
        "event_type": event_type,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "repo": payload.get("repository", {}).get("full_name", ""),
    }

    handlers = {
        "pull_request": _normalize_pull_request,
        "pull_request_review": _normalize_pr_review,
        "push": _normalize_push,
        "issues": _normalize_issue,
    }

    handler = handlers.get(event_type, _normalize_generic)
    return {**base, **handler(payload)}


def _normalize_pull_request(payload: dict) -> dict:
    pr = payload.get("pull_request", {})
    return {
        "action": payload.get("action"),
        "pr_number": pr.get("number"),
        "pr_id": pr.get("id"),
        "pr_title": pr.get("title"),
        "author": pr.get("user", {}).get("login"),
        "state": pr.get("state"),
        "created_at": pr.get("created_at"),
        "updated_at": pr.get("updated_at"),
        "merged_at": pr.get("merged_at"),
        "closed_at": pr.get("closed_at"),
        "additions": pr.get("additions", 0),
        "deletions": pr.get("deletions", 0),
        "changed_files": pr.get("changed_files", 0),
        "requested_reviewers": [r.get("login") for r in pr.get("requested_reviewers", [])],
        "head_sha": pr.get("head", {}).get("sha"),
        "base_branch": pr.get("base", {}).get("ref"),
    }


def _normalize_pr_review(payload: dict) -> dict:
    review = payload.get("review", {})
    pr = payload.get("pull_request", {})
    return {
        "action": payload.get("action"),
        "pr_number": pr.get("number"),
        "pr_id": pr.get("id"),
        "reviewer": review.get("user", {}).get("login"),
        "review_state": review.get("state"),
        "submitted_at": review.get("submitted_at"),
    }


def _normalize_push(payload: dict) -> dict:
    return {
        "ref": payload.get("ref"),
        "before": payload.get("before"),
        "after": payload.get("after"),
        "pusher": payload.get("pusher", {}).get("name"),
        "commit_count": len(payload.get("commits", [])),
    }


def _normalize_issue(payload: dict) -> dict:
    issue = payload.get("issue", {})
    return {
        "action": payload.get("action"),
        "issue_number": issue.get("number"),
        "issue_id": issue.get("id"),
        "author": issue.get("user", {}).get("login"),
        "state": issue.get("state"),
        "created_at": issue.get("created_at"),
    }


def _normalize_generic(payload: dict) -> dict:
    return {"raw_payload": payload}
