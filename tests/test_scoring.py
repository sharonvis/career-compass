from copy import deepcopy

import pytest

from services.scoring_service import (
    calculate_career_readiness,
    calculate_confirmed_skill_gap,
    calculate_skill_credit,
    select_next_action,
)


@pytest.mark.parametrize("required_level", [0, -1])
def test_nonpositive_required_level_raises(required_level):
    with pytest.raises(ValueError, match="^required_level must be greater than 0$"):
        calculate_skill_credit(required_level)


def test_demonstrated_credit():
    assert calculate_skill_credit(3, demonstrated_level=2) == pytest.approx(2 / 3)


def test_demonstrated_credit_is_capped():
    assert calculate_skill_credit(2, demonstrated_level=3) == 1.0


def test_demonstrated_zero_overrides_high_claim():
    assert calculate_skill_credit(3, claimed_level=3, demonstrated_level=0) == 0.0


def test_unassessed_claim_is_discounted():
    assert calculate_skill_credit(3, claimed_level=2) == pytest.approx(0.5 * 2 / 3)


def test_overclaim_is_capped_before_discount():
    assert calculate_skill_credit(1, claimed_level=3) == 0.5


def test_zero_claim_gives_zero_credit():
    assert calculate_skill_credit(3, claimed_level=0) == 0.0


def test_negative_claim_gives_zero_credit():
    assert calculate_skill_credit(3, claimed_level=-1) == 0.0


def test_negative_demonstrated_level_gives_zero_credit():
    assert calculate_skill_credit(3, claimed_level=3, demonstrated_level=-1) == 0.0


def test_custom_unassessed_factor():
    assert calculate_skill_credit(3, claimed_level=3, unassessed_factor=0.25) == 0.25


def test_empty_skills_raise():
    with pytest.raises(ValueError):
        calculate_career_readiness([])


def test_no_valid_skills_raise():
    skills = [
        {"required_level": 0, "importance": 5},
        {"required_level": -1, "importance": 2},
        {"required_level": 3, "importance": 0},
    ]
    with pytest.raises(ValueError):
        calculate_career_readiness(skills)


@pytest.mark.parametrize("required_level", [0, 3])
def test_negative_importance_raises(required_level):
    with pytest.raises(ValueError, match="importance must not be negative"):
        calculate_career_readiness([
            {"required_level": required_level, "importance": -1}
        ])


def test_fully_demonstrated_readiness():
    skills = [{"required_level": 3, "importance": 5, "demonstrated_level": 3}]
    assert calculate_career_readiness(skills) == pytest.approx(1.0)


def test_unassessed_readiness():
    skills = [{"required_level": 3, "importance": 5, "claimed_level": 3}]
    assert calculate_career_readiness(skills) == pytest.approx(0.5)


@pytest.mark.parametrize(
    "demonstrated_importance, claimed_importance, expected",
    [(3, 1, 0.875), (1, 3, 0.625)],
)
def test_weighted_readiness(demonstrated_importance, claimed_importance, expected):
    skills = [
        {"required_level": 3, "importance": demonstrated_importance,
         "demonstrated_level": 3},
        {"required_level": 2, "importance": claimed_importance,
         "claimed_level": 2, "demonstrated_level": None},
    ]
    assert calculate_career_readiness(skills) == pytest.approx(expected)


@pytest.mark.parametrize("required_level", [0, -1])
def test_invalid_required_level_is_ignored(required_level):
    skills = [
        {"required_level": required_level, "importance": 100},
        {"required_level": 3, "importance": 1, "demonstrated_level": 3},
    ]
    assert calculate_career_readiness(skills) == pytest.approx(1.0)


def test_zero_importance_is_ignored():
    skills = [
        {"required_level": 3, "importance": 0},
        {"required_level": 3, "importance": 1, "demonstrated_level": 3},
    ]
    assert calculate_career_readiness(skills) == pytest.approx(1.0)


def test_missing_skill_levels_use_defaults():
    skills = [{"required_level": 3, "importance": 5}]
    assert calculate_career_readiness(skills) == pytest.approx(0.0)


def test_custom_readiness_unassessed_factor():
    skills = [
        {"required_level": 3, "importance": 3, "demonstrated_level": 3},
        {"required_level": 2, "importance": 1, "claimed_level": 2},
    ]
    assert calculate_career_readiness(
        skills, unassessed_factor=0.25
    ) == pytest.approx(0.8125)


@pytest.mark.parametrize(
    "levels, factor, expected",
    [({"claimed_level": -1}, 0.5, 0.0),
     ({"demonstrated_level": 10}, 0.5, 1.0),
     ({"claimed_level": 3}, 2.0, 1.0),
     ({"claimed_level": 3}, -1.0, 0.0)],
)
def test_readiness_stays_in_range(levels, factor, expected):
    skills = [{"required_level": 3, "importance": 1, **levels}]
    result = calculate_career_readiness(skills, unassessed_factor=factor)
    assert 0.0 <= result <= 1.0
    assert result == pytest.approx(expected)


def test_unassessed_confirmed_gap_is_none():
    assert calculate_confirmed_skill_gap(3, demonstrated_level=None) is None


@pytest.mark.parametrize(
    "required_level, demonstrated_level, expected",
    [(3, 0, 3), (3, 1, 2), (3, 3, 0), (2, 3, 0), (3, -2, 3)],
)
def test_assessed_confirmed_gap(required_level, demonstrated_level, expected):
    result = calculate_confirmed_skill_gap(required_level, demonstrated_level)
    assert result == expected
    assert isinstance(result, int)


@pytest.mark.parametrize(
    "required_level, demonstrated_level",
    [(0, 1), (-1, 1), (0, None)],
)
def test_nonpositive_required_level_raises_for_confirmed_gap(
    required_level, demonstrated_level
):
    with pytest.raises(ValueError) as error:
        calculate_confirmed_skill_gap(required_level, demonstrated_level)
    assert str(error.value) == "required_level must be greater than 0."


def test_confirmed_gap_defaults_to_unassessed():
    assert calculate_confirmed_skill_gap(required_level=3) is None


def test_empty_next_action():
    assert select_next_action([]) is None


def test_all_assessed_without_gaps():
    skills = [
        {"name": "SQL", "required_level": 2, "importance": 4,
         "demonstrated_level": 2, "assessable": True},
        {"name": "Statistics", "required_level": 2, "importance": 4,
         "demonstrated_level": 3, "assessable": True},
    ]
    assert select_next_action(skills) is None


def test_confirmed_gap_beats_higher_importance_assessment():
    skills = [
        {"name": "Statistics", "required_level": 2, "importance": 100,
         "claimed_level": 2, "assessable": True},
        {"name": "SQL", "required_level": 2, "importance": 1,
         "demonstrated_level": 1},
    ]
    assert select_next_action(skills) == {"action_type": "improve", "skill_name": "SQL"}


def test_improve_ranks_by_importance_times_gap():
    skills = [
        {"name": "SQL", "required_level": 3, "importance": 3,
         "demonstrated_level": 1},
        {"name": "Statistics", "required_level": 3, "importance": 5,
         "demonstrated_level": 2},
    ]
    assert select_next_action(skills) == {"action_type": "improve", "skill_name": "SQL"}


def test_improve_tie_uses_stable_priority():
    skills = [
        {"name": "Statistics", "required_level": 3, "importance": 2,
         "demonstrated_level": 1, "stable_priority": 2},
        {"name": "SQL", "required_level": 2, "importance": 4,
         "demonstrated_level": 1, "stable_priority": 1},
    ]
    assert select_next_action(skills) == {"action_type": "improve", "skill_name": "SQL"}


@pytest.mark.parametrize("demonstrated_level", [0, -2])
def test_zero_and_negative_demonstrated_levels_have_full_gap(demonstrated_level):
    skills = [
        {"name": "Statistics", "required_level": 3, "importance": 2,
         "demonstrated_level": 1},
        {"name": "SQL", "required_level": 3, "importance": 2,
         "demonstrated_level": demonstrated_level},
    ]
    assert select_next_action(skills) == {"action_type": "improve", "skill_name": "SQL"}


def test_assessed_skill_without_gap_is_not_reassessed():
    skills = [{"name": "SQL", "required_level": 2, "importance": 4,
               "demonstrated_level": 2, "claimed_level": 3, "assessable": True}]
    assert select_next_action(skills) is None


@pytest.mark.parametrize(
    "sql_values, statistics_values",
    [
        ({"importance": 5, "claimed_level": 0, "stable_priority": 9},
         {"importance": 4, "claimed_level": 2, "stable_priority": 1}),
        ({"claimed_level": 2, "stable_priority": 9},
         {"claimed_level": 1, "stable_priority": 1}),
        ({"claimed_level": 1, "stable_priority": 1},
         {"claimed_level": 1, "stable_priority": 2}),
    ],
    ids=["importance", "unverified_claim", "stable_priority"],
)
def test_assessment_ranking(sql_values, statistics_values):
    skills = [
        {"name": "Statistics", "required_level": 2, "importance": 4,
         "assessable": True, **statistics_values},
        {"name": "SQL", "required_level": 2, "importance": 4,
         "assessable": True, **sql_values},
    ]
    assert select_next_action(skills) == {"action_type": "assess", "skill_name": "SQL"}


def test_assessment_claim_is_capped():
    skills = [
        {"name": "Statistics", "required_level": 2, "importance": 4,
         "claimed_level": 100, "assessable": True, "stable_priority": 2},
        {"name": "SQL", "required_level": 2, "importance": 4,
         "claimed_level": 2, "assessable": True, "stable_priority": 1},
    ]
    assert select_next_action(skills) == {"action_type": "assess", "skill_name": "SQL"}


def test_negative_and_missing_claims_default_to_zero_for_ranking():
    skills = [
        {"name": "Statistics", "required_level": 2, "importance": 4,
         "claimed_level": -2, "assessable": True, "stable_priority": 2},
        {"name": "SQL", "required_level": 2, "importance": 4,
         "assessable": True, "stable_priority": 1},
    ]
    assert select_next_action(skills) == {"action_type": "assess", "skill_name": "SQL"}


@pytest.mark.parametrize("optional_values", [{"assessable": False}, {}])
def test_unassessable_skills_are_not_selected(optional_values):
    skills = [{"name": "SQL", "required_level": 2, "importance": 4,
               "claimed_level": 3, **optional_values}]
    assert select_next_action(skills) is None


def test_next_action_negative_importance_raises():
    skills = [
        {"name": "SQL", "required_level": 2, "importance": 4,
         "demonstrated_level": 1},
        {"name": "Statistics", "required_level": 0, "importance": -1},
    ]
    with pytest.raises(ValueError) as error:
        select_next_action(skills)
    assert str(error.value) == "importance must not be negative"


@pytest.mark.parametrize(
    "required_level, importance", [(2, 0), (0, 4), (-1, 4)]
)
def test_next_action_skips_invalid_skills(required_level, importance):
    skills = [{"name": "SQL", "required_level": required_level,
               "importance": importance, "demonstrated_level": 0,
               "assessable": True}]
    assert select_next_action(skills) is None


@pytest.mark.parametrize("demonstrated_level, action_type", [(None, "assess"), (1, "improve")])
def test_stable_priority_defaults_and_input_order(demonstrated_level, action_type):
    skills = [
        {"name": "Statistics", "required_level": 2, "importance": 4,
         "demonstrated_level": demonstrated_level, "assessable": True},
        {"name": "SQL", "required_level": 2, "importance": 4,
         "demonstrated_level": demonstrated_level, "assessable": True,
         "stable_priority": 100},
    ]
    expected = {"action_type": action_type, "skill_name": "SQL"}
    assert select_next_action(skills) == expected
    assert select_next_action(list(reversed(skills))) == expected


@pytest.mark.parametrize("demonstrated_level", [None, 1])
def test_next_action_does_not_mutate_input(demonstrated_level):
    skills = [{"name": "SQL", "required_level": 2, "importance": 4,
               "demonstrated_level": demonstrated_level, "assessable": True}]
    original = deepcopy(skills)
    select_next_action(skills)
    assert skills == original


@pytest.mark.parametrize("demonstrated_level, action_type", [(None, "assess"), (1, "improve")])
def test_next_action_return_structure(demonstrated_level, action_type):
    skills = [{"name": "SQL", "required_level": 2, "importance": 4,
               "claimed_level": 3, "demonstrated_level": demonstrated_level,
               "assessable": True, "stable_priority": 1}]
    result = select_next_action(skills)
    assert result == {"action_type": action_type, "skill_name": "SQL"}
    assert set(result) == {"action_type", "skill_name"}


def test_golden_persona_next_action():
    skills = [
        {"name": "SQL", "required_level": 2, "importance": 4,
         "claimed_level": 3, "demonstrated_level": None, "assessable": True},
        {"name": "Statistics", "required_level": 2, "importance": 4,
         "claimed_level": 1, "demonstrated_level": None, "assessable": True},
    ]
    assert select_next_action(skills) == {"action_type": "assess", "skill_name": "SQL"}

    skills[0]["demonstrated_level"] = 1
    assert select_next_action(skills) == {"action_type": "improve", "skill_name": "SQL"}
