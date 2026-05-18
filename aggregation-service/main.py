import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from metrics import (
    get_author_metrics,
    get_open_prs,
    get_pr_metrics,
    get_repo_metrics,
    persist_event,
    upsert_pull_request,
    upsert_review,
)
from models import Base

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:dev@localhost:5432/analytics"
)
SERVICE_BUS_CONN_STR = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING", "")

logger = logging.getLogger(__name__)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

app = FastAPI(title="Aggregation Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _process_event(event: dict) -> None:
    async with AsyncSessionLocal() as session:
        event_type = event.get("event_type", "")
        try:
            await persist_event(session, event)
            if event_type == "pull_request":
                await upsert_pull_request(session, event)
            elif event_type == "pull_request_review":
                await upsert_review(session, event)
        except Exception:
            logger.exception("Failed to process event %s", event.get("event_id"))


async def _consume_service_bus() -> None:
    if not SERVICE_BUS_CONN_STR:
        logger.info("[DEV] No Service Bus connection string — consumer inactive")
        return

    from azure.servicebus.aio import ServiceBusClient

    topics = ["pull-request-events", "review-events", "push-events", "issue-events"]
    subscription = "aggregation-sub"

    async with ServiceBusClient.from_connection_string(SERVICE_BUS_CONN_STR) as client:
        receivers = [
            client.get_subscription_receiver(topic_name=t, subscription_name=subscription)
            for t in topics
        ]
        async with asyncio.TaskGroup() as tg:
            for receiver in receivers:
                tg.create_task(_drain_receiver(receiver))


async def _drain_receiver(receiver) -> None:
    async with receiver:
        async for msg in receiver:
            try:
                event = json.loads(str(msg))
                await _process_event(event)
                await receiver.complete_message(msg)
            except Exception:
                logger.exception("Failed to handle Service Bus message")
                await receiver.abandon_message(msg)


@app.on_event("startup")
async def startup():
    for attempt in range(10):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            break
        except Exception as exc:
            if attempt == 9:
                raise
            logger.warning("DB not ready (attempt %d/10): %s — retrying in 3s", attempt + 1, exc)
            await asyncio.sleep(3)
    asyncio.create_task(_consume_service_bus())


@app.get("/health")
async def health():
    return {"status": "ok", "service": "aggregation"}


@app.get("/metrics/pr/{pr_id}")
async def pr_metrics(pr_id: int):
    async with AsyncSessionLocal() as session:
        result = await get_pr_metrics(session, pr_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"PR {pr_id} not found")
    return result


@app.get("/metrics/author/{github_login}")
async def author_metrics(github_login: str):
    async with AsyncSessionLocal() as session:
        return await get_author_metrics(session, github_login)


@app.get("/metrics/repo/{repo:path}")
async def repo_metrics(repo: str):
    async with AsyncSessionLocal() as session:
        return await get_repo_metrics(session, repo)


@app.get("/prs/open")
async def open_prs(repo: str | None = None, limit: int = 50):
    async with AsyncSessionLocal() as session:
        return await get_open_prs(session, repo=repo, limit=limit)


@app.post("/events")
async def receive_event(event: dict):
    """Direct event ingestion — used in local dev when Azure Service Bus is not configured."""
    await _process_event(event)
    return {"status": "processed", "event_id": event.get("event_id")}
