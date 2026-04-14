"""Seed the clause library and contract templates from JSON corpus files.

Usage:
    PYTHONPATH=packages/ancol-common/src python3 scripts/seed_clause_library.py
    PYTHONPATH=packages/ancol-common/src python3 scripts/seed_clause_library.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus" / "data"
CLAUSE_LIBRARY_FILE = CORPUS_DIR / "clause_library.json"
TEMPLATE_DATA_FILE = CORPUS_DIR / "contract_templates.json"

# System user for created_by FK
SYSTEM_USER_ID = "a0000000-0000-0000-0000-000000000001"


async def seed_clauses(dry_run: bool = False) -> int:
    """Load clause_library.json and upsert into ClauseLibrary table."""
    if not CLAUSE_LIBRARY_FILE.exists():
        logger.error("Clause library file not found: %s", CLAUSE_LIBRARY_FILE)
        return 0

    with open(CLAUSE_LIBRARY_FILE) as f:
        clauses = json.load(f)

    logger.info("Loaded %d clauses from %s", len(clauses), CLAUSE_LIBRARY_FILE.name)

    if dry_run:
        from collections import Counter

        types = Counter(c["contract_type"] for c in clauses)
        for t, count in sorted(types.items()):
            logger.info("  %s: %d clauses", t, count)
        logger.info("DRY RUN — no database changes")
        return len(clauses)

    import uuid

    from ancol_common.db.connection import get_session
    from ancol_common.db.models import ClauseLibrary
    from sqlalchemy import select

    inserted = 0
    skipped = 0

    async with get_session() as session:
        for clause in clauses:
            # Check if clause already exists (natural key: type + category + version)
            result = await session.execute(
                select(ClauseLibrary).where(
                    ClauseLibrary.contract_type == clause["contract_type"],
                    ClauseLibrary.clause_category == clause["clause_category"],
                    ClauseLibrary.version == clause.get("version", 1),
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                skipped += 1
                continue

            record = ClauseLibrary(
                id=uuid.uuid4(),
                contract_type=clause["contract_type"],
                clause_category=clause["clause_category"],
                title_id=clause["title_id"],
                title_en=clause.get("title_en"),
                text_id=clause["text_id"],
                text_en=clause.get("text_en"),
                risk_notes=clause.get("risk_notes"),
                is_mandatory=clause.get("is_mandatory", False),
                version=clause.get("version", 1),
                is_active=True,
                created_by=uuid.UUID(SYSTEM_USER_ID),
            )
            session.add(record)
            inserted += 1

    logger.info("Clauses: %d inserted, %d skipped (already exist)", inserted, skipped)
    return inserted


async def seed_templates(dry_run: bool = False) -> int:
    """Load contract_templates.json and upsert into ContractTemplate table."""
    if not TEMPLATE_DATA_FILE.exists():
        logger.error("Template file not found: %s", TEMPLATE_DATA_FILE)
        return 0

    with open(TEMPLATE_DATA_FILE) as f:
        templates = json.load(f)

    logger.info("Loaded %d templates from %s", len(templates), TEMPLATE_DATA_FILE.name)

    if dry_run:
        for t in templates:
            req = len(t.get("required_clauses", []))
            opt = len(t.get("optional_clauses", []))
            logger.info("  %s: %d required, %d optional", t["contract_type"], req, opt)
        logger.info("DRY RUN — no database changes")
        return len(templates)

    import uuid

    from ancol_common.db.connection import get_session
    from ancol_common.db.models import ContractTemplate
    from sqlalchemy import select

    inserted = 0
    skipped = 0

    async with get_session() as session:
        for tmpl in templates:
            result = await session.execute(
                select(ContractTemplate).where(
                    ContractTemplate.contract_type == tmpl["contract_type"],
                    ContractTemplate.version == tmpl.get("version", 1),
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                skipped += 1
                continue

            record = ContractTemplate(
                id=uuid.uuid4(),
                name=tmpl["name"],
                contract_type=tmpl["contract_type"],
                version=tmpl.get("version", 1),
                description=tmpl.get("description"),
                required_clauses=tmpl.get("required_clauses"),
                optional_clauses=tmpl.get("optional_clauses"),
                default_terms=tmpl.get("default_terms"),
                is_active=True,
            )
            session.add(record)
            inserted += 1

    logger.info("Templates: %d inserted, %d skipped (already exist)", inserted, skipped)
    return inserted


async def main(dry_run: bool = False) -> None:
    clause_count = await seed_clauses(dry_run)
    template_count = await seed_templates(dry_run)
    logger.info("Done: %d clauses, %d templates processed", clause_count, template_count)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed clause library and contract templates")
    parser.add_argument("--dry-run", action="store_true", help="Preview without database changes")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
