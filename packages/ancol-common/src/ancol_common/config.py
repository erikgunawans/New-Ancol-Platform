"""Environment-based configuration for all services."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    # GCP
    gcp_project: str = os.getenv("GCP_PROJECT", "ancol-mom-compliance")
    gcp_region: str = os.getenv("GCP_REGION", "asia-southeast2")

    # Database
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "ancol_compliance")
    db_user: str = os.getenv("DB_USER", "ancol")
    db_password: str = os.getenv("DB_PASSWORD", "")

    # Cloud Storage
    bucket_raw: str = os.getenv("BUCKET_RAW", "ancol-mom-raw")
    bucket_processed: str = os.getenv("BUCKET_PROCESSED", "ancol-mom-processed")
    bucket_reports: str = os.getenv("BUCKET_REPORTS", "ancol-mom-reports")

    # Pub/Sub
    pubsub_topic_prefix: str = os.getenv("PUBSUB_TOPIC_PREFIX", "mom")

    # Gemini
    gemini_flash_model: str = os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    gemini_pro_model: str = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")

    # Vertex AI Search
    vertex_search_datastore: str = os.getenv(
        "VERTEX_SEARCH_DATASTORE",
        "projects/ancol-mom-compliance/locations/asia-southeast2/"
        "collections/default_collection/dataStores/regulatory-corpus",
    )

    # Document AI
    document_ai_processor: str = os.getenv("DOCUMENT_AI_PROCESSOR", "")

    # Notifications
    sendgrid_api_key: str = os.getenv("SENDGRID_API_KEY", "")
    notification_from_email: str = os.getenv("NOTIFICATION_FROM", "compliance@ancol.co.id")

    # HITL
    hitl_sla_hours: int = int(os.getenv("HITL_SLA_HOURS", "48"))
    auto_flag_confidence_threshold: float = float(
        os.getenv("AUTO_FLAG_CONFIDENCE_THRESHOLD", "0.80")
    )

    # Email ingest
    email_ingest_address: str = os.getenv("EMAIL_INGEST_ADDRESS", "corpsec@ancol.co.id")
    email_scan_interval_minutes: int = int(os.getenv("EMAIL_SCAN_INTERVAL_MINUTES", "15"))

    # Batch processing
    batch_default_concurrency: int = int(os.getenv("BATCH_DEFAULT_CONCURRENCY", "10"))
    batch_max_concurrency: int = int(os.getenv("BATCH_MAX_CONCURRENCY", "50"))
    batch_max_retries: int = int(os.getenv("BATCH_MAX_RETRIES", "3"))

    # Integrations
    board_portal_url: str = os.getenv("BOARD_PORTAL_URL", "")
    board_portal_api_key: str = os.getenv("BOARD_PORTAL_API_KEY", "")
    erp_api_url: str = os.getenv("ERP_API_URL", "")
    erp_api_key: str = os.getenv("ERP_API_KEY", "")

    # BigQuery
    bq_dataset: str = os.getenv("BQ_DATASET", "ancol_compliance_analytics")

    # Environment
    environment: str = os.getenv("ENVIRONMENT", "dev")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
