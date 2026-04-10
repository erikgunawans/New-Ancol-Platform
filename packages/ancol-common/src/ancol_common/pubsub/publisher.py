"""Cloud Pub/Sub message publishing helper."""

from __future__ import annotations

import json
import logging
from functools import lru_cache

from google.cloud import pubsub_v1

from ancol_common.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def _get_publisher() -> pubsub_v1.PublisherClient:
    return pubsub_v1.PublisherClient()


def publish_message(
    topic_key: str,
    data: dict,
    attributes: dict[str, str] | None = None,
) -> str:
    """Publish a JSON message to a Pub/Sub topic.

    Args:
        topic_key: Short topic name (e.g., "mom-uploaded"). Will be prefixed.
        data: Message payload (will be JSON-serialized).
        attributes: Optional message attributes.

    Returns:
        Published message ID.
    """
    settings = get_settings()
    topic_name = f"ancol-{topic_key}"
    topic_path = _get_publisher().topic_path(settings.gcp_project, topic_name)

    message_bytes = json.dumps(data).encode("utf-8")
    future = _get_publisher().publish(
        topic_path,
        data=message_bytes,
        **(attributes or {}),
    )
    message_id = future.result(timeout=30)
    logger.info("Published message %s to %s", message_id, topic_name)
    return message_id
