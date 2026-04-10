"""Gemini API client factory using google-genai SDK."""

from __future__ import annotations

from functools import lru_cache

from google import genai
from google.genai.types import HttpOptions

from ancol_common.config import get_settings


@lru_cache
def get_gemini_client() -> genai.Client:
    """Create a Gemini client configured for Vertex AI in asia-southeast2."""
    settings = get_settings()
    return genai.Client(
        vertexai=True,
        project=settings.gcp_project,
        location=settings.gcp_region,
        http_options=HttpOptions(api_version="v1"),
    )


def get_flash_model() -> str:
    """Return the Gemini Flash model ID."""
    return get_settings().gemini_flash_model


def get_pro_model() -> str:
    """Return the Gemini Pro model ID."""
    return get_settings().gemini_pro_model
