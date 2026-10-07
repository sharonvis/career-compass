import pytest

from services.scoring_service import (
    are_prerequisites_satisfied,
    calculate_career_readiness,
    calculate_confirmed_skill_gap,
    classify_opportunity_match,
    select_next_action,
)


def build_student_skills():
    """Build fresh AI/ML requirements and initial student evidence."""
    return [
        {"name": "Python", "required_level": 2, "importance": 5,
         "claimed_level": 2, "demonstrated_level": 2,
         "assessable": False, "stable_priority": 1},
        {"name": "SQL", "required_level": 2, "importance": 4,
         "claimed_level": 3, "demonstrated_level": None,
         "assessable": True, "stable_priority": 2},
        {"name": "Statistics", "required_level": 2, "importance": 4,
         "claimed_level": 1, "demonstrated_level": None,
         "assessable": True, "stable_priority": 3},
        {"name": "ML Fundamentals", "required_level": 2, "importance": 5,
         "claimed_level": 1, "demonstrated_level": None,
         "assessable": False, "stable_priority": 4,
         "prerequisites": [
             {"skill_name": "Python", "minimum_level": 1},
             {"skill_name": "Statistics", "minimum_level": 1},
         ]},
        {"name": "Pandas", "required_level": 2, "importance": 4,
         "claimed_level": 2, "demonstrated_level": None,
         "assessable": False, "stable_priority": 5,
         "prerequisites": [{"skill_name": "Python", "minimum_level": 1}]},
        {"name": "Git", "required_level": 1, "importance": 2,
         "claimed_level": 1, "demonstrated_level": None,
         "assessable": False, "stable_priority": 6},
    ]


def find_skill(skills, name):
    return next(skill for skill in skills if skill["name"] == name)


def demonstrated_levels(skills):
    return {skill["name"]: skill["demonstrated_level"] for skill in skills}


def build_opportunity_skills(skills):
    return [
        {"name": name, "required_level": 2,
         "claimed_level": find_skill(skills, name)["claimed_level"],
         "demonstrated_level": find_skill(skills, name)["demonstrated_level"]}
        for name in ["Python", "SQL"]
    ]


def test_full_golden_persona_flow():
    hard_filters = {"degree": True, "batch": True, "location": True}

    # Step 1: initial state.
    initial_skills = build_student_skills()
    assert calculate_career_readiness(
        initial_skills, unassessed_factor=1.0
    ) == pytest.approx(19.5 / 24)
    initial_readiness = calculate_career_readiness(initial_skills)
    assert initial_readiness == pytest.approx(12.25 / 24)
    assert select_next_action(initial_skills) == {
        "action_type": "assess", "skill_name": "SQL"
    }
    initial_levels = demonstrated_levels(initial_skills)
    assert initial_levels["Statistics"] is None
    assert are_prerequisites_satisfied(
        find_skill(initial_skills, "ML Fundamentals")["prerequisites"], initial_levels
    ) is False
    assert are_prerequisites_satisfied(
        find_skill(initial_skills, "Pandas")["prerequisites"], initial_levels
    ) is True
    assert classify_opportunity_match(
        hard_filters, build_opportunity_skills(initial_skills)
    ) == "good"

    # Step 2: SQL Form A, using fresh data.
    form_a_skills = build_student_skills()
    sql_a = find_skill(form_a_skills, "SQL")
    sql_a["demonstrated_level"] = 1
    form_a_readiness = calculate_career_readiness(form_a_skills)
    assert form_a_readiness == pytest.approx(12.25 / 24)
    assert form_a_readiness == pytest.approx(initial_readiness)
    assert calculate_confirmed_skill_gap(
        sql_a["required_level"], sql_a["demonstrated_level"]
    ) == 1
    assert select_next_action(form_a_skills) == {
        "action_type": "improve", "skill_name": "SQL"
    }
    assert classify_opportunity_match(
        hard_filters, build_opportunity_skills(form_a_skills)
    ) == "stretch"

    # Step 3: SQL Form B, using fresh data.
    form_b_skills = build_student_skills()
    sql_b = find_skill(form_b_skills, "SQL")
    sql_b["demonstrated_level"] = 2
    form_b_readiness = calculate_career_readiness(form_b_skills)
    assert form_b_readiness == pytest.approx(14.25 / 24)
    assert form_b_readiness > form_a_readiness
    assert calculate_confirmed_skill_gap(
        sql_b["required_level"], sql_b["demonstrated_level"]
    ) == 0
    assert select_next_action(form_b_skills) == {
        "action_type": "assess", "skill_name": "Statistics"
    }
    assert classify_opportunity_match(
        hard_filters, build_opportunity_skills(form_b_skills)
    ) == "strong"
    form_b_levels = demonstrated_levels(form_b_skills)
    assert form_b_levels["Statistics"] is None
    assert are_prerequisites_satisfied(
        find_skill(form_b_skills, "ML Fundamentals")["prerequisites"], form_b_levels
    ) is False
