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


def live_skill_rows(session, oid):
    return session.execute(select(models.Skill.name, models.OpportunitySkill.required_level,
                                  models.OpportunitySkill.is_required).join(models.OpportunitySkill)
                           .where(models.OpportunitySkill.opportunity_id == oid)
                           .order_by(models.Skill.name)).all()


def mapping_record(text, **kwargs):
    return opportunity(mapping_text=[{"context": "ambiguous", "text": text}], **kwargs)


def test_live_mappings_idempotent_and_canonical(session):
    record = mapping_record("Required: Python SQL PostgreSQL")
    first = persist_normalized_opportunities(session, [record])
    second = persist_normalized_opportunities(session, [record])
    assert first["opportunity_ids"] == second["opportunity_ids"]
    oid = first["opportunity_ids"][0]
    assert live_skill_rows(session, oid) == [("Python", 1, True), ("SQL", 1, True)]
    assert session.scalar(select(func.count()).select_from(models.Skill)) == 10


def test_refresh_removes_old_changes_flags_and_preserves_row_id(session):
    oid = persist_normalized_opportunities(session, [mapping_record("Required: Python SQL")])["opportunity_ids"][0]
    result = persist_normalized_opportunities(session, [mapping_record("Required: Git. Preferred: Python")])
    assert result["opportunity_ids"] == [oid]
    assert live_skill_rows(session, oid) == [("Git", 1, True), ("Python", 1, False)]


def test_missing_mapping_metadata_does_not_erase(session):
    oid = persist_normalized_opportunities(session, [mapping_record("Required: SQL")])["opportunity_ids"][0]
    persist_normalized_opportunities(session, [opportunity()])
    persist_normalized_opportunities(session, [opportunity(mapping_text=[])])
    assert live_skill_rows(session, oid) == [("SQL", 1, True)]


def test_fresh_unrecognized_text_clears_live_mappings(session):
    oid = persist_normalized_opportunities(session, [mapping_record("Required: SQL")])["opportunity_ids"][0]
    persist_normalized_opportunities(session, [mapping_record("Required: enthusiasm")])
    assert live_skill_rows(session, oid) == []
    assert session.get(models.Opportunity, oid) is not None


def test_only_optional_mappings_kept_but_excluded_from_ranking(session):
    from services import user_service, opportunity_service
    user = user_service.create_user(session, "Student", "optional@example.com", "BSc", "CS", 1)
    cid = user_service.list_careers(session)[0]["career_id"]
    oid = persist_normalized_opportunities(session, [mapping_record("Preferred: SQL")])["opportunity_ids"][0]
    assert live_skill_rows(session, oid) == [("SQL", 1, False)]
    assert oid not in {o["opportunity_id"] for o in opportunity_service.get_ranked_opportunities(session, user["user_id"], cid)}


def test_seeded_mappings_untouched_even_with_matching_live_title(session):
    seeded = session.scalar(select(models.Opportunity).where(models.Opportunity.is_seeded.is_(True)))
    before = live_skill_rows(session, seeded.id)
    record = mapping_record("Required: Excel", title=seeded.title, company=seeded.company, location=seeded.location)
    oid = persist_normalized_opportunities(session, [record])["opportunity_ids"][0]
    assert oid != seeded.id
    assert live_skill_rows(session, seeded.id) == before
    assert seeded.source == "seed" and seeded.is_seeded is True


def test_mapping_updates_level_to_inferred_baseline(session):
    oid = persist_normalized_opportunities(session, [mapping_record("Required: SQL")])["opportunity_ids"][0]
    row = session.scalar(select(models.OpportunitySkill).where(models.OpportunitySkill.opportunity_id == oid))
    row.required_level = 3
    session.flush()
    persist_normalized_opportunities(session, [mapping_record("Required: SQL")])
    assert row.required_level == 1


def test_insert_and_mapping_rollback_together(session):
    before = session.scalar(select(func.count()).select_from(models.Opportunity))
    oid = persist_normalized_opportunities(session, [mapping_record("Required: Python SQL")])["opportunity_ids"][0]
    assert len(live_skill_rows(session, oid)) == 2
    session.rollback()
    assert session.scalar(select(func.count()).select_from(models.Opportunity)) == before
    assert session.get(models.Opportunity, oid) is None
    assert live_skill_rows(session, oid) == []


def test_refresh_rollback_restores_existing_mappings(session):
    oid = persist_normalized_opportunities(session, [mapping_record("Required: Python SQL")])["opportunity_ids"][0]
    session.commit()
    persist_normalized_opportunities(session, [mapping_record("Required: Git")])
    session.rollback()
    assert live_skill_rows(session, oid) == [("Python", 1, True), ("SQL", 1, True)]
