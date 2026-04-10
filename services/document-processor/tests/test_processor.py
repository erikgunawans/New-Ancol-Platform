"""Tests for the core document processing logic."""

from __future__ import annotations

from document_processor.processor import _resolve_mime_type


def test_resolve_mime_type_from_content_type():
    assert _resolve_mime_type("application/pdf", "doc.pdf") == "application/pdf"
    assert _resolve_mime_type("image/png", "scan.png") == "image/png"


def test_resolve_mime_type_from_extension():
    assert _resolve_mime_type("application/octet-stream", "doc.pdf") == "application/pdf"
    assert _resolve_mime_type("", "scan.png") == "image/png"
    assert _resolve_mime_type("", "scan.jpg") == "image/jpeg"
    assert _resolve_mime_type("", "scan.tiff") == "image/tiff"


def test_resolve_mime_type_unknown_defaults_to_pdf():
    assert _resolve_mime_type("", "document") == "application/pdf"
    assert _resolve_mime_type("", "unknown.xyz") == "application/pdf"
