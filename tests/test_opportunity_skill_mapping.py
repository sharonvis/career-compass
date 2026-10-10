"""Pure deterministic qualification mapping, without database or API calls."""
import pytest
from services.opportunity_skill_mapping_service import infer_skill_mappings


def mapped(text, context="ambiguous"):
    return {row["skill_name"]: row for row in infer_skill_mappings([{"text": text, "context": context}])}


@pytest.mark.parametrize("text,names", [
    ("Required: Python and SQL", {"Python", "SQL"}),
    ("Essential: ML and Pandas", {"Machine Learning Fundamentals", "Pandas/Data Handling"}),
    ("Mandatory: machine learning and pandas", {"Machine Learning Fundamentals", "Pandas/Data Handling"}),
    ("Qualifications:\nPython\nSQL", {"Python", "SQL"}),
    ("Python is required, SQL is required", {"Python", "SQL"}),
])
def test_explicit_required_skills(text, names):
    rows = mapped(text)
    assert set(rows) == names
    assert all(row["is_required"] and row["required_level"] == 1 for row in rows.values())


@pytest.mark.parametrize("cue", ["Preferred", "Optional", "Nice to have", "Bonus"])
def test_optional_wording(cue):
    rows = mapped(f"{cue}: Python and Git")
    assert set(rows) == {"Python", "Git"}
    assert all(not row["is_required"] for row in rows.values())


def test_required_wins_over_optional():
    rows = mapped("Required: Python\nPreferred: Python, SQL")
    assert rows["Python"]["is_required"] is True
    assert rows["SQL"]["is_required"] is False


@pytest.mark.parametrize("text", ["SQL is not required", "No SQL experience required", "We do not require SQL", "Required: SQL is not required", "Not required: SQL"])
def test_negation(text):
    assert mapped(text) == {}


def test_negation_does_not_suppress_separate_requirement():
    assert set(mapped("SQL is not required, Python is required")) == {"Python"}
    assert set(mapped("Required: Python, not SQL")) == {"Python"}
    assert mapped("SQL isn't required") == {}


def test_negated_but_preferred_is_optional():
    assert mapped("SQL is not required but preferred") == {}
    assert mapped("SQL is optional, not required")["SQL"]["is_required"] is False


def test_boundaries_and_no_indirect_inference():
    assert mapped("Required: AI, GitHub, data, pythonic, nosql, excelsior, xml, ml") == {}
    assert set(mapped("Required: ML, Git, SQL, Excel")) == {"Machine Learning Fundamentals", "Git", "SQL", "Excel"}


def test_alias_deduplication():
    rows = mapped("Required: SQL, PostgreSQL, MySQL, sql, machine learning, ML")
    assert set(rows) == {"SQL", "Machine Learning Fundamentals"}


def test_ambiguous_mentions_and_unknown_skills_are_not_required():
    assert mapped("We use Python and SQL. Enthusiasm for data.") == {}
    assert mapped("Required: enthusiasm, Java and Rust") == {}


def test_all_catalog_aliases():
    names = mapped("Required: Python SQL statistics machine learning pandas git data structures OOP Excel data visualisation")
    assert len(names) == 10


def test_responsibilities_reset_required_section():
    assert set(mapped("Requirements:\nPython\nResponsibilities:\nSQL")) == {"Python"}
