"""Gmail inbox scanner — finds MoM attachments and uploads to pipeline.

Polls the Corporate Secretary's Gmail inbox for emails with MoM-like
attachments (PDF, Word, scans). Downloads attachments, uploads to GCS
raw bucket, and publishes mom-uploaded events to trigger the pipeline.
"""

from __future__ import annotations

import base64
import logging
import re

from ancol_common.config import get_settings
from ancol_common.pubsub.publisher import publish_message
from ancol_common.utils import SYSTEM_USER_ID
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# MoM attachment detection patterns
MOM_FILENAME_PATTERNS = [
    re.compile(r"risalah|notulen|minutes|mom|rapat", re.IGNORECASE),
    re.compile(r"rups|rupslb|rupst", re.IGNORECASE),
    re.compile(r"direksi|komisaris|board", re.IGNORECASE),
]

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}
ALLOWED_MIMETYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png",
    "image/jpeg",
    "image/tiff",
}

_EXTENSION_TO_CONTENT_TYPE: dict[str, str] = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


def _get_content_type(filename: str) -> str:
    """Get MIME content type from filename extension."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _EXTENSION_TO_CONTENT_TYPE.get(ext, "application/pdf")

# Gmail label for processed emails
PROCESSED_LABEL = "MoM-Processed"


def _get_gmail_service(credentials_path: str | None = None):
    """Build Gmail API service using service account credentials."""
    settings = get_settings()
    if credentials_path:
        creds = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            subject=settings.email_ingest_address,
        )
    else:
        creds = service_account.Credentials.from_service_account_info(
            {},
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _is_mom_attachment(filename: str, mimetype: str) -> bool:
    """Check if an attachment looks like a MoM document."""
    if mimetype not in ALLOWED_MIMETYPES:
        return False

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return False

    return any(pat.search(filename) for pat in MOM_FILENAME_PATTERNS)


def _detect_mom_type(subject: str, filename: str) -> str:
    """Detect MoM type from email subject or filename."""
    text = (subject + " " + filename).lower()
    if any(k in text for k in ["sirkuler", "circular", "keputusan sirkuler"]):
        return "circular"
    if any(k in text for k in ["luar biasa", "extraordinary", "rupslb"]):
        return "extraordinary"
    return "regular"


def _extract_meeting_date(subject: str) -> str | None:
    """Try to extract meeting date from email subject."""
    from ancol_common.utils import parse_indonesian_date

    return parse_indonesian_date(subject)


async def scan_inbox(max_results: int = 20) -> list[dict]:
    """Scan Gmail inbox for new MoM attachments.

    Returns list of processed attachments with their document IDs.
    """
    get_settings()
    results = []

    try:
        service = _get_gmail_service()
    except Exception:
        logger.warning("Gmail API not configured, skipping scan")
        return results

    # Search for unread emails with attachments, not yet processed
    query = "has:attachment -label:MoM-Processed is:unread"

    try:
        response = (
            service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        )
    except Exception:
        logger.exception("Failed to list Gmail messages")
        return results

    messages = response.get("messages", [])
    logger.info("Found %d unread messages with attachments", len(messages))

    for msg_meta in messages:
        try:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_meta["id"], format="full")
                .execute()
            )

            headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
            subject = headers.get("subject", "")
            sender = headers.get("from", "")

            # Process attachments
            attachments = _extract_attachments(msg["payload"])

            for att in attachments:
                if not _is_mom_attachment(att["filename"], att["mimeType"]):
                    continue

                logger.info("Found MoM attachment: %s from %s", att["filename"], sender)

                # Download attachment data
                att_data = (
                    service.users()
                    .messages()
                    .attachments()
                    .get(userId="me", messageId=msg_meta["id"], id=att["attachmentId"])
                    .execute()
                )

                file_data = base64.urlsafe_b64decode(att_data["data"])

                # Upload to GCS and trigger pipeline
                result = await _upload_to_pipeline(
                    filename=att["filename"],
                    content=file_data,
                    subject=subject,
                    sender=sender,
                    email_message_id=msg_meta["id"],
                )
                results.append(result)

        except Exception:
            logger.exception("Failed to process message %s", msg_meta["id"])

    return results


def _extract_attachments(payload: dict) -> list[dict]:
    """Recursively extract attachments from Gmail message payload."""
    attachments = []
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("filename") and part.get("body", {}).get("attachmentId"):
                attachments.append(
                    {
                        "filename": part["filename"],
                        "mimeType": part.get("mimeType", ""),
                        "attachmentId": part["body"]["attachmentId"],
                        "size": part["body"].get("size", 0),
                    }
                )
            attachments.extend(_extract_attachments(part))
    return attachments


async def _upload_to_pipeline(
    filename: str,
    content: bytes,
    subject: str,
    sender: str,
    email_message_id: str,
) -> dict:
    """Upload an attachment to GCS and trigger the document processing pipeline."""
    import uuid

    settings = get_settings()
    doc_id = str(uuid.uuid4())

    from ancol_common.utils import detect_document_format, get_gcs_client

    doc_format = detect_document_format(filename)

    gcs_client = get_gcs_client()
    bucket = gcs_client.bucket(settings.bucket_raw)
    blob_name = f"email-ingest/{doc_id}/{filename}"
    blob = bucket.blob(blob_name)
    blob.metadata = {
        "document_id": doc_id,
        "source": "email-ingest",
        "email_sender": sender,
        "email_subject": subject,
        "email_message_id": email_message_id,
    }
    content_type = _get_content_type(filename)
    blob.upload_from_string(content, content_type=content_type)

    gcs_raw_uri = f"gs://{settings.bucket_raw}/{blob_name}"

    # Detect MoM metadata
    mom_type = _detect_mom_type(subject, filename)
    meeting_date = _extract_meeting_date(subject)

    # Create document in DB
    from ancol_common.db.connection import get_session
    from ancol_common.db.models import Document

    async with get_session() as session:
        document = Document(
            id=uuid.UUID(doc_id),
            filename=filename,
            format=doc_format,
            file_size_bytes=len(content),
            gcs_raw_uri=gcs_raw_uri,
            status="pending",
            mom_type=mom_type,
            meeting_date=meeting_date,
            is_confidential=False,
            uploaded_by=uuid.UUID(SYSTEM_USER_ID),
        )
        session.add(document)

    # Publish upload event
    publish_message(
        "mom-uploaded",
        {
            "document_id": doc_id,
            "bucket": settings.bucket_raw,
            "name": blob_name,
            "contentType": content_type,
            "size": str(len(content)),
            "metadata": {
                "document_id": doc_id,
                "source": "email-ingest",
                "email_sender": sender,
            },
        },
    )

    logger.info("Email attachment uploaded: doc=%s, file=%s", doc_id, filename)

    return {
        "document_id": doc_id,
        "filename": filename,
        "mom_type": mom_type,
        "meeting_date": meeting_date,
        "source": "email-ingest",
        "email_sender": sender,
    }
