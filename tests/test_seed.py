"""Seed acceptance tests; all database work is isolated in memory."""

from copy import deepcopy
from datetime import date, timedelta
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, event, func, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database import db, models as m, seed
from services.scoring_service import calculate_career_readiness, classify_opportunity_match


@pytest.fixture
def test_engine():
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    db.configure_sqlite_foreign_keys(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session(test_engine):
    db.Base.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session


def counts(session):
    return {table.name: session.scalar(select(func.count()).select_from(table))
            for table in db.Base.metadata.sorted_tables}


def load_fresh(module_name, filename):
    spec = importlib.util.spec_from_file_location(module_name, filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_init_db_is_explicit(test_engine, tmp_path, monkeypatch):
    target = tmp_path / "data" / "test.db"
    monkeypatch.setattr(db, "DATABASE_PATH", target)
    monkeypatch.setattr(db, "engine", test_engine)
    assert not target.parent.exists()
    assert inspect(test_engine).get_table_names() == []
    db.init_db()
    assert target.parent.is_dir()
    assert set(inspect(test_engine).get_table_names()) == set(db.Base.metadata.tables)
    assert not target.exists()  # The injected engine stays in memory.


def test_db_import_has_no_side_effects(test_engine, monkeypatch):
    import sqlalchemy
    factory = Mock(return_value=test_engine)
    monkeypatch.setattr(sqlalchemy, "create_engine", factory)
    with monkeypatch.context() as context:
        context.setattr(test_engine, "connect", Mock(side_effect=AssertionError("Import connected")))
        context.setattr(Path, "mkdir", Mock(side_effect=AssertionError("Import created a directory")))
        load_fresh("isolated_seed_db", Path(db.__file__))
    assert inspect(test_engine).get_table_names() == []


def test_seed_import_has_no_writes(test_engine, monkeypatch):
    writes = []
    event.listen(test_engine, "before_cursor_execute", lambda *args: writes.append(args[2]))
    with monkeypatch.context() as context:
        context.setattr(db.engine, "connect", Mock(side_effect=AssertionError("Production connection")))
        context.setattr(db.SessionLocal, "__call__", Mock(side_effect=AssertionError("Production session")))
        context.setattr(Session, "flush", Mock(side_effect=AssertionError("Import flushed")))
        context.setattr(Session, "execute", Mock(side_effect=AssertionError("Import executed SQL")))
        load_fresh("isolated_seed_catalog", Path(seed.__file__))
    assert writes == []


def test_seed_counts_and_idempotence(session):
    first = seed.seed_database(session)
    session.commit()
    expected = dict(skills=10, careers=3, career_skill_requirements=17,
                    skill_prerequisites=6, opportunities=10, opportunity_skills=42)
    actual = counts(session)
    for table, number in expected.items():
        assert actual[table] == number
    assert first == {"created": sum(expected.values()), "updated": 0}
    assert seed.seed_database(session) == {"created": 0, "updated": 0}
    session.commit()
    assert counts(session) == actual
    for name, number in [("AI/ML Engineer", 6), ("Software Engineer", 5), ("Data Analyst", 6)]:
        career = session.scalar(select(m.Career).filter_by(name=name))
        assert len(career.skill_requirements) == number


def test_frozen_career_requirements(session):
    seed.seed_database(session)
    actual = {career.name: {r.skill.name: (r.required_level, r.importance)
                           for r in career.skill_requirements}
              for career in session.scalars(select(m.Career))}
    assert actual == {
        "AI/ML Engineer": {"Python": (2, 5), "Machine Learning Fundamentals": (2, 5),
                           "SQL": (2, 4), "Statistics": (2, 4), "Pandas/Data Handling": (2, 4), "Git": (1, 2)},
        "Software Engineer": {"Python": (2, 4), "Data Structures & Algorithms": (2, 5),
                              "Object-Oriented Programming": (2, 4), "Git": (2, 3), "SQL": (1, 2)},
        "Data Analyst": {"SQL": (2, 5), "Excel": (2, 4), "Statistics": (2, 4),
                         "Data Visualization": (2, 4), "Pandas/Data Handling": (2, 3), "Python": (1, 3)},
    }


def test_frozen_prerequisites_and_acyclic_graph(session):
    seed.seed_database(session)
    edges = {(p.skill.name, p.prerequisite_skill.name, p.minimum_level)
             for p in session.scalars(select(m.SkillPrerequisite))}
    assert edges == {
        ("Machine Learning Fundamentals", "Python", 1),
        ("Machine Learning Fundamentals", "Statistics", 1),
        ("Pandas/Data Handling", "Python", 1),
        ("Data Structures & Algorithms", "Python", 1),
        ("Object-Oriented Programming", "Python", 1),
        ("Data Visualization", "Statistics", 1),
    }
    # Independent topological elimination, rather than the validator's DFS.
    remaining = {s.name for s in session.scalars(select(m.Skill))}
    while remaining:
        ready = {name for name in remaining
                 if not any(a == name and b in remaining for a, b, level in edges)}
        assert ready, "Prerequisite cycle detected"
        remaining -= ready


def test_reconcile_values_preserve_deadlines_and_extra_rows(session, monkeypatch):
    seed.seed_database(session)
    session.commit()
    requirement = session.scalar(select(m.CareerSkillRequirement).join(m.Career).join(m.Skill)
                                 .where(m.Career.name == "AI/ML Engineer", m.Skill.name == "Python"))
    requirement.required_level, requirement.importance = 3, 1
    skill = session.scalar(select(m.Skill).filter_by(name="Python"))
    skill.description = "Changed"
    career = session.scalar(select(m.Career).filter_by(name="AI/ML Engineer"))
    career.description = "Changed"
    prerequisite = session.scalars(select(m.SkillPrerequisite)).first()
    prerequisite.minimum_level = 3
    opportunity = session.scalars(select(m.Opportunity)).first()
    opportunity.location, opportunity.is_seeded = "Changed", False
    opportunity_skill = opportunity.skills[0]
    opportunity_skill.required_level = 3
    session.add(m.Skill(name="User-added skill"))
    session.commit()
    deadlines = {o.id: o.deadline for o in session.scalars(select(m.Opportunity))}
    class FutureDate(date):
        @classmethod
        def today(cls):
            return date(2099, 1, 1)
    monkeypatch.setattr(seed, "date", FutureDate)
    result = seed.seed_database(session)
    session.commit()
    assert result == {"created": 0, "updated": 6}
    assert (requirement.required_level, requirement.importance) == (2, 5)
    assert skill.description != "Changed" and career.description != "Changed"
    assert prerequisite.minimum_level == 1
    assert opportunity.location == "Chennai" and opportunity.is_seeded is True
    assert opportunity_skill.required_level == 2
    assert {o.id: o.deadline for o in session.scalars(select(m.Opportunity))} == deadlines
    assert session.scalar(select(m.Skill).filter_by(name="User-added skill")) is not None


def test_seeded_opportunities_and_no_runtime_data(session):
    seed.seed_database(session)
    opportunities = list(session.scalars(select(m.Opportunity).order_by(m.Opportunity.id)))
    assert [(o.title, o.company, o.location, o.opportunity_type) for o in opportunities] == [
        ("Machine Learning Intern", "Nova Labs", "Chennai", "internship"),
        ("AI Research Assistant Intern", "Tessera AI", "Bengaluru", "internship"),
        ("Junior Data Scientist Trainee", "Vertex Analytics", "Hyderabad", "entry_level"),
        ("Data Engineering Intern", "DataNest", "Remote", "internship"),
        ("Software Development Intern", "BrightPath Technologies", "Chennai", "internship"),
        ("Backend Developer Intern", "Cobalt Ridge Software", "Pune", "internship"),
        ("Associate Software Engineer", "Lumen Works", "Bengaluru", "entry_level"),
        ("Data Analyst Intern", "Saffron Data Co", "Chennai", "internship"),
        ("Business Analytics Intern", "Vertex Analytics", "Remote", "internship"),
        ("Junior Data Analyst", "Harbor Light Digital", "Hyderabad", "entry_level"),
    ]
    for opportunity in opportunities:
        assert opportunity.source == "seed" and opportunity.source_url is None
        assert opportunity.is_seeded is True
        assert opportunity.deadline > date.today()
        assert any(s.is_required for s in opportunity.skills)
    for model in [m.User, m.Application, m.AssessmentAttempt, m.AttemptAnswer,
                  m.Evidence, m.ProgressEvent, m.RoadmapCompletion]:
        assert session.scalar(select(func.count()).select_from(model)) == 0


def test_frozen_opportunity_skill_requirements(session):
    seed.seed_database(session)
    actual = {o.title: {(s.skill.name, s.required_level, s.is_required) for s in o.skills}
              for o in session.scalars(select(m.Opportunity))}
    assert actual == {
        "Machine Learning Intern": {("Python", 2, True), ("Machine Learning Fundamentals", 1, True), ("Pandas/Data Handling", 1, True), ("Git", 1, False)},
        "AI Research Assistant Intern": {("Python", 2, True), ("Statistics", 2, True), ("Machine Learning Fundamentals", 2, True), ("SQL", 1, False)},
        "Junior Data Scientist Trainee": {("Python", 2, True), ("SQL", 2, True), ("Statistics", 2, True), ("Pandas/Data Handling", 2, True), ("Machine Learning Fundamentals", 1, True)},
        "Data Engineering Intern": {("Python", 2, True), ("SQL", 2, True), ("Git", 1, False)},
        "Software Development Intern": {("Python", 2, True), ("Data Structures & Algorithms", 2, True), ("Git", 1, True), ("Object-Oriented Programming", 1, True)},
        "Backend Developer Intern": {("Python", 2, True), ("Object-Oriented Programming", 2, True), ("SQL", 1, True), ("Git", 2, True)},
        "Associate Software Engineer": {("Python", 2, True), ("Data Structures & Algorithms", 2, True), ("Object-Oriented Programming", 2, True), ("Git", 1, True), ("SQL", 2, False)},
        "Data Analyst Intern": {("SQL", 2, True), ("Excel", 2, True), ("Data Visualization", 1, True), ("Statistics", 1, False)},
        "Business Analytics Intern": {("Excel", 2, True), ("Data Visualization", 2, True), ("Statistics", 1, True), ("SQL", 1, True)},
        "Junior Data Analyst": {("SQL", 2, True), ("Python", 1, True), ("Pandas/Data Handling", 2, True), ("Statistics", 2, True), ("Data Visualization", 2, True)},
    }


def test_deadline_offset_applied_on_first_insert(session, monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2030, 1, 1)
    monkeypatch.setattr(seed, "date", FixedDate)
    seed.seed_database(session)
    opportunity = session.scalar(select(m.Opportunity).filter_by(title="Machine Learning Intern"))
    assert opportunity.deadline == date(2030, 1, 1) + timedelta(days=30)


def test_skill_order(session):
    seed.seed_database(session)
    assert list(session.scalars(select(m.Skill.name).order_by(m.Skill.id))) == [
        "Python", "SQL", "Statistics", "Machine Learning Fundamentals", "Pandas/Data Handling",
        "Git", "Data Structures & Algorithms", "Object-Oriented Programming", "Excel", "Data Visualization",
    ]


@pytest.mark.parametrize("case", [
    "unknown_requirement", "unknown_prerequisite", "unknown_opportunity",
    "requirement_level_zero", "requirement_level_four", "prerequisite_level_zero", "prerequisite_level_four",
    "opportunity_level_zero", "opportunity_level_four", "importance", "self", "career_pair", "prerequisite_pair",
    "opportunity_key", "opportunity_pair", "cycle",
])
def test_invalid_constants_fail_before_any_writes(session, monkeypatch, case):
    requirements = deepcopy(seed.CAREER_REQUIREMENTS)
    prerequisites = deepcopy(seed.PREREQUISITES)
    opportunities = deepcopy(seed.OPPORTUNITIES)
    if case == "unknown_requirement":
        requirements[0] = ("AI/ML Engineer", "Unknown", 2, 5)
    elif case == "unknown_prerequisite":
        prerequisites[0] = ("Python", "Unknown", 1)
    elif case == "unknown_opportunity":
        opportunities[0]["skills"][0] = ("Unknown", 2, True)
    elif case.startswith("requirement_level"):
        requirements[0] = ("AI/ML Engineer", "Python", 0 if case.endswith("zero") else 4, 5)
    elif case.startswith("prerequisite_level"):
        prerequisites[0] = ("Machine Learning Fundamentals", "Python", 0 if case.endswith("zero") else 4)
    elif case.startswith("opportunity_level"):
        opportunities[0]["skills"][0] = ("Python", 0 if case.endswith("zero") else 4, True)
    elif case == "importance":
        requirements[0] = ("AI/ML Engineer", "Python", 2, 0)
    elif case == "self":
        prerequisites[0] = ("Python", "Python", 1)
    elif case == "career_pair":
        requirements.append(requirements[0])
    elif case == "prerequisite_pair":
        prerequisites.append(prerequisites[0])
    elif case == "opportunity_key":
        opportunities.append(deepcopy(opportunities[0]))
    elif case == "opportunity_pair":
        opportunities[0]["skills"].append(opportunities[0]["skills"][0])
    elif case == "cycle":
        prerequisites.append(("Python", "Machine Learning Fundamentals", 1))
    monkeypatch.setattr(seed, "CAREER_REQUIREMENTS", requirements)
    monkeypatch.setattr(seed, "PREREQUISITES", prerequisites)
    monkeypatch.setattr(seed, "OPPORTUNITIES", opportunities)
    statements = []
    event.listen(session.bind, "before_cursor_execute", lambda *args: statements.append(args[2]))
    with pytest.raises(ValueError):
        seed.seed_database(session)
    assert statements == []
    assert not session.new
    assert all(number == 0 for number in counts(session).values())


def test_caller_can_rollback(session):
    seed.seed_database(session)
    session.rollback()
    assert all(number == 0 for number in counts(session).values())


def test_golden_persona_integration(session):
    seed.seed_database(session)
    career = session.scalar(select(m.Career).filter_by(name="AI/ML Engineer"))
    claims = {"Python": 2, "SQL": 3, "Statistics": 1, "Machine Learning Fundamentals": 1,
              "Pandas/Data Handling": 2, "Git": 1}
    requirements = [dict(name=r.skill.name, required_level=r.required_level, importance=r.importance,
                         claimed_level=claims[r.skill.name],
                         demonstrated_level=2 if r.skill.name == "Python" else None)
                    for r in career.skill_requirements]
    assert calculate_career_readiness(requirements) == pytest.approx(12.25 / 24)
    assert calculate_career_readiness(requirements) == pytest.approx(0.51, abs=0.001)
    opportunity = session.scalar(select(m.Opportunity).filter_by(title="Data Engineering Intern"))
    for sql_level, expected in [(1, "stretch"), (2, "strong")]:
        skills = [dict(name=s.skill.name, required_level=s.required_level,
                       claimed_level=claims[s.skill.name],
                       demonstrated_level=sql_level if s.skill.name == "SQL" else 2)
                  for s in opportunity.skills if s.is_required]
        assert classify_opportunity_match({"location": True}, skills) == expected
