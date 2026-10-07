"""Persistence contracts for normalized live opportunities."""

from datetime import date

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database import models
from database.db import Base, configure_sqlite_foreign_keys
from database.seed import seed_database
from services.opportunity_persistence_service import persist_normalized_opportunities


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    configure_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_database(session)
            session.commit()
            yield session
    finally:
        engine.dispose()


def opportunity(**overrides):
    record = {
        "title": "Software Engineering Intern",
        "company": "Example Labs",
        "location": "Bengaluru, India",
        "opportunity_type": "internship",
        "source": "serpapi",
        "source_url": "https://example.com/jobs/123",
        "deadline": date(2026, 12, 31),
        "is_seeded": False,
    }
    record.update(overrides)
    return record


def test_inserts_new_live_opportunity(session):
    result = persist_normalized_opportunities(session, [opportunity()])

    row = session.get(models.Opportunity, result["opportunity_ids"][0])
    assert result["created"] == 1
    assert result["updated"] == result["unchanged"] == result["skipped"] == 0
    assert row.title == "Software Engineering Intern"
    assert row.company == "Example Labs"
    assert row.location == "Bengaluru, India"
    assert row.opportunity_type == "internship"
    assert row.source == "serpapi" and row.is_seeded is False
    assert row.source_url == "https://example.com/jobs/123"
    assert row.deadline == date(2026, 12, 31)


def test_inserts_multiple_opportunities(session):
    records = [
        opportunity(),
        opportunity(title="Junior Analyst", company="Data Co", location=None, deadline=None),
    ]

    result = persist_normalized_opportunities(session, records)

    assert result["created"] == 2
    assert len(result["opportunity_ids"]) == 2
    assert session.scalar(
        select(func.count()).select_from(models.Opportunity).where(
            models.Opportunity.source == "serpapi",
        )
    ) == 2


def test_repeated_persistence_is_idempotent(session):
    record = opportunity()
    first = persist_normalized_opportunities(session, [record])
    second = persist_normalized_opportunities(session, [record])

    assert second["created"] == 0
    assert second["updated"] == 0
    assert second["unchanged"] == 1
    assert first["opportunity_ids"] == second["opportunity_ids"]
    assert session.scalar(
        select(models.Opportunity.id).where(
            models.Opportunity.source == "serpapi",
            models.Opportunity.title == record["title"],
        )
    ) == first["opportunity_ids"][0]


def test_existing_live_listing_updates_safe_fields_and_preserves_id(session):
    first = persist_normalized_opportunities(session, [opportunity()])
    updated = opportunity(
        source_url="https://example.com/jobs/updated",
        deadline=date(2027, 1, 15),
    )

    result = persist_normalized_opportunities(session, [updated])

    row = session.get(models.Opportunity, first["opportunity_ids"][0])
    assert result["updated"] == 1
    assert result["opportunity_ids"] == first["opportunity_ids"]
    assert row.source_url == "https://example.com/jobs/updated"
    assert row.deadline == date(2027, 1, 15)


def test_seeded_rows_remain_separate_from_live_rows(session):
    seeded = session.scalar(select(models.Opportunity).where(
        models.Opportunity.source == "seed",
    ))
    live = opportunity(
        title=seeded.title,
        company=seeded.company,
        location=seeded.location,
    )

    result = persist_normalized_opportunities(session, [live])

    assert result["created"] == 1
    assert result["opportunity_ids"][0] != seeded.id
    assert seeded.source == "seed" and seeded.is_seeded is True


def test_rejects_seeded_or_wrong_source_records_without_mutation(session):
    result = persist_normalized_opportunities(session, [
        opportunity(is_seeded=True),
        opportunity(source="seed"),
        opportunity(source_url="file:///tmp/job"),
    ])

    assert result["skipped"] == 3
    assert result["created"] == 0


@pytest.mark.parametrize(
    "record",
    [
        None,
        {},
        opportunity(title=" "),
        opportunity(company=""),
        opportunity(location=4),
        opportunity(opportunity_type="contract"),
        opportunity(deadline="2026-12-31"),
        opportunity(source_url="not a URL"),
    ],
)
def test_invalid_records_are_skipped_safely(session, record):
    result = persist_normalized_opportunities(session, [record])

    assert result["skipped"] == 1
    assert result["created"] == 0
    assert session.scalar(
        select(models.Opportunity.id).where(models.Opportunity.source == "serpapi")
    ) is None


def test_duplicate_inputs_are_deduplicated_deterministically(session):
    first_record = opportunity()
    duplicate = opportunity(
        title=" software engineering intern ",
        company="EXAMPLE LABS",
        location=" Bengaluru, India ",
        source_url="https://example.com/jobs/duplicate",
    )

    result = persist_normalized_opportunities(session, [first_record, duplicate])

    assert result["created"] == 1
    assert result["duplicate_inputs"] == 1
    assert len(result["opportunity_ids"]) == 1
    assert session.get(models.Opportunity, result["opportunity_ids"][0]).source_url == first_record["source_url"]


def test_caller_can_roll_back_persisted_opportunities(session):
    result = persist_normalized_opportunities(session, [opportunity()])
    assert result["created"] == 1

    session.rollback()

    assert session.scalar(
        select(models.Opportunity.id).where(models.Opportunity.source == "serpapi")
    ) is None


def test_non_list_input_is_rejected(session):
    with pytest.raises(ValueError, match="must be a list"):
        persist_normalized_opportunities(session, opportunity())
