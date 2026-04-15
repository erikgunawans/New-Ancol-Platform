# Changelog

All notable changes to the Ancol MoM Compliance System will be documented in this file.

## [0.1.0.0] - 2026-04-15

### Added
- Contract PDF generation with styled A4 HTML output via WeasyPrint, including clause boxes with risk badges, party tables, key terms, and confidence scores
- `POST /api/drafting/pdf` endpoint for generating contract draft PDFs from the clause library and AI review
- Contract detail page (`/contracts/[id]`) with metadata cards, clause viewer, obligations table, and risk analysis tabs
- Draft generator page (`/contracts/draft`) with contract type picker, party builder, key terms editor, markdown preview, and PDF export
- "Buat Draf" sidebar link under Contract Management
- 13 new tests for PDF HTML generation and the drafting endpoint (277 total)
- Shared contract label constants (`web/src/lib/contracts.ts`) for status, type, risk, and obligation maps

### Fixed
- PDF export now reuses the previewed draft instead of re-drafting (prevents divergence between preview and export)
- Clause text in PDF preserves line breaks via `white-space: pre-wrap`
- Obligations permission errors (403) distinguished from empty data on contract detail page
- Blob URL memory leak on PDF export (revoked after 10 seconds)
- `window.open` for PDF export uses `noopener,noreferrer` to prevent opener reference leakage
- CSS class value in PDF HTML now HTML-escaped for defense-in-depth
- PDF fallback path handling uses `os.path.splitext` instead of fragile `.replace()`
