"""Cloud Pub/Sub push message handler for FastAPI services."""

from __future__ import annotations

import base64
import json
import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PubSubPushMessage(BaseModel):
    """Pub/Sub push subscription message envelope."""

    message: PubSubMessage
    subscription: str


class PubSubMessage(BaseModel):
    """Individual Pub/Sub message."""

    data: str  # Base64-encoded
    message_id: str
    publish_time: str
    attributes: dict[str, str] = {}


def decode_pubsub_message(push_message: PubSubPushMessage) -> dict:
    """Decode a Pub/Sub push message into a Python dict.

    Args:
        push_message: The push subscription envelope.

    Returns:
        Decoded JSON payload.
    """
    raw_data = base64.b64decode(push_message.message.data)
    payload = json.loads(raw_data)
    logger.info(
        "Decoded Pub/Sub message %s from %s",
        push_message.message.message_id,
        push_message.subscription,
    )
    return payload
