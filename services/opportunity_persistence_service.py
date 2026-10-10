"""Persist normalized live opportunities; callers own the transaction."""

from collections.abc import Mapping
from datetime import date, datetime
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Opportunity, OpportunitySkill, Skill
from services.opportunity_skill_mapping_service import infer_skill_mappings


LIVE_OPPORTUNITY_SOURCE = "serpapi"


def _clean_identity(value):
    return " ".join(value.split()).casefold()


def _deduplication_key(opportunity):
    return (
        opportunity["source"],
        _clean_identity(opportunity["title"]),
        _clean_identity(opportunity["company"]),
        _clean_identity(opportunity["location"] or ""),
    )


def _valid_opportunity(record):
    if not isinstance(record, Mapping):
        return False
    if record.get("source") != LIVE_OPPORTUNITY_SOURCE or record.get("is_seeded") is not False:
        return False
    for field in ("title", "company", "opportunity_type", "source_url"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            return False
    if record["opportunity_type"] not in {"internship", "entry_level"}:
        return False
    location = record.get("location")
    if location is not None and (not isinstance(location, str) or not location.strip()):
        return False
    source_url = record["source_url"].strip()
    parsed_url = urlparse(source_url)
    if parsed_url.scheme.lower() not in {"http", "https"} or not parsed_url.netloc:
        return False
    deadline = record.get("deadline")
    if deadline is not None and (not isinstance(deadline, date) or isinstance(deadline, datetime)):
        return False
    return True


def _sync_live_skills(session, row, record):
    """Live mappings are ingestion-owned; absent metadata never erases them."""
    parts = record.get("mapping_text")
    if not isinstance(parts, list) or not parts or not all(
        isinstance(part, Mapping) and isinstance(part.get("text"), str)
        and part["text"].strip() for part in parts
    ):
        return
    if row.is_seeded or row.source != LIVE_OPPORTUNITY_SOURCE:
        return
    inferred = infer_skill_mappings(parts)
    names = {item["skill_name"] for item in inferred}
    ids = dict(session.execute(select(Skill.name, Skill.id).where(Skill.name.in_(names))).all())
    desired = {ids[item["skill_name"]]: item for item in inferred if item["skill_name"] in ids}
    existing = {item.skill_id: item for item in session.scalars(
        select(OpportunitySkill).where(OpportunitySkill.opportunity_id == row.id)
    )}
    for skill_id, mapping in existing.items():
        if skill_id not in desired:
            session.delete(mapping)
    for skill_id, item in desired.items():
        mapping = existing.get(skill_id)
        if mapping is None:
            mapping = OpportunitySkill(opportunity_id=row.id, skill_id=skill_id)
            session.add(mapping)
        mapping.required_level = item["required_level"]
        mapping.is_required = item["is_required"]
    # Make refreshes visible to a second ingestion in the same transaction.
    session.flush()


def persist_normalized_opportunities(
    session: Session,
    opportunities: list[dict],
) -> dict[str, object]:
    """Insert/update normalized live rows idempotently without committing.

    Duplicate incoming natural keys keep the first record in the batch. For an
    existing live listing, only its type, source URL, and deadline are refreshed;
    identity fields and the seeded flag are never changed. Supplied mapping_text
    also synchronizes ingestion-owned live skills; it is never a model column.
    Result counters retain their Opportunity-row meaning.
    """
    if not isinstance(opportunities, list):
        raise ValueError("opportunities must be a list")

    result = {
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "duplicate_inputs": 0,
        "opportunity_ids": [],
    }

    with session.no_autoflush:
        existing_rows = list(session.scalars(
            select(Opportunity).where(
                Opportunity.source == LIVE_OPPORTUNITY_SOURCE,
                Opportunity.is_seeded.is_(False),
            ).order_by(Opportunity.id)
        ))
        existing = {}
        for row in existing_rows:
            key = _deduplication_key({
                "source": row.source,
                "title": row.title,
                "company": row.company,
                "location": row.location,
            })
            existing.setdefault(key, row)
        seen_inputs = set()

        for record in opportunities:
            if not _valid_opportunity(record):
                result["skipped"] += 1
                continue

            key = _deduplication_key(record)
            if key in seen_inputs:
                result["duplicate_inputs"] += 1
                continue
            seen_inputs.add(key)

            values = {
                "title": " ".join(record["title"].split()),
                "company": " ".join(record["company"].split()),
                "location": " ".join(record["location"].split()) if record.get("location") else None,
                "opportunity_type": record["opportunity_type"],
                "source": LIVE_OPPORTUNITY_SOURCE,
                "source_url": record["source_url"].strip(),
                "deadline": record.get("deadline"),
                "is_seeded": False,
            }
            row = existing.get(key)
            if row is None:
                row = Opportunity(**values)
                session.add(row)
                session.flush()
                existing[key] = row
                result["created"] += 1
            else:
                changes = {
                    field: value
                    for field, value in values.items()
                    if field in {"opportunity_type", "source_url", "deadline"}
                    and getattr(row, field) != value
                }
                if changes:
                    for field, value in changes.items():
                        setattr(row, field, value)
                    result["updated"] += 1
                else:
                    result["unchanged"] += 1
            _sync_live_skills(session, row, record)
            result["opportunity_ids"].append(row.id)

    session.flush()
    return result
