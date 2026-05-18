import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SERVICE_BUS_CONN_STR = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING", "")
AGGREGATION_URL = os.getenv("AGGREGATION_URL", "http://localhost:8002")

TOPIC_MAP = {
    "pull_request": "pull-request-events",
    "pull_request_review": "review-events",
    "push": "push-events",
    "issues": "issue-events",
}


async def publish_event(event_type: str, payload: dict[str, Any]) -> None:
    topic = TOPIC_MAP.get(event_type, "generic-events")

    if not SERVICE_BUS_CONN_STR:
        # Local dev: forward directly to aggregation service via HTTP
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"{AGGREGATION_URL}/events", json=payload, timeout=5.0)
            logger.info("[DEV] Forwarded event to aggregation: topic=%s event_id=%s", topic, payload.get("event_id"))
        except Exception as exc:
            logger.warning("[DEV] Could not forward to aggregation (%s): %s", AGGREGATION_URL, exc)
        return

    from azure.servicebus.aio import ServiceBusClient

    async with ServiceBusClient.from_connection_string(SERVICE_BUS_CONN_STR) as client:
        async with client.get_topic_sender(topic_name=topic) as sender:
            from azure.servicebus import ServiceBusMessage
            msg = ServiceBusMessage(json.dumps(payload))
            await sender.send_messages(msg)
