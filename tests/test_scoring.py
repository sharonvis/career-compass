from copy import deepcopy

import pytest

from services.scoring_service import (
    are_prerequisites_satisfied,
    calculate_career_readiness,
    calculate_confirmed_skill_gap,
    calculate_skill_credit,
    classify_opportunity_match,
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


@pytest.mark.parametrize(
    "skills",
    [[], [{"name": "SQL", "required_level": 2, "demonstrated_level": 2}]],
)
def test_failed_hard_filter_returns_not_eligible(skills):
    assert classify_opportunity_match(
        {"degree": True, "location": False}, skills
    ) == "not_eligible"


@pytest.mark.parametrize(
    "skill_values, expected",
    [
        ({"demonstrated_level": 2}, "strong"),
        ({"demonstrated_level": 3}, "strong"),
        ({"demonstrated_level": 1}, "stretch"),
        ({"demonstrated_level": 0}, "stretch"),
        ({"demonstrated_level": 1, "claimed_level": 3}, "stretch"),
        ({"demonstrated_level": None, "claimed_level": 2}, "good"),
        ({"demonstrated_level": None, "claimed_level": 1}, "stretch"),
        ({"demonstrated_level": None}, "stretch"),
        ({"claimed_level": 2}, "good"),
        ({"demonstrated_level": -2}, "stretch"),
    ],
    ids=["meets", "exceeds", "gap", "zero", "high_claim_with_gap",
         "unassessed_meets", "unassessed_below", "missing_claim",
         "missing_demonstration", "negative_demonstration"],
)
def test_single_skill_match_band(skill_values, expected):
    skills = [{"name": "SQL", "required_level": 2, **skill_values}]
    assert classify_opportunity_match({}, skills) == expected


def test_all_unassessed_claims_meet_requirements():
    skills = [
        {"name": "Python", "required_level": 2, "claimed_level": 2},
        {"name": "SQL", "required_level": 2, "claimed_level": 3},
    ]
    assert classify_opportunity_match({"degree": True}, skills) == "good"


def test_confirmed_gap_beats_good_unassessed_skills():
    skills = [
        {"name": "Python", "required_level": 2, "claimed_level": 2},
        {"name": "SQL", "required_level": 2, "demonstrated_level": 1},
    ]
    assert classify_opportunity_match({}, skills) == "stretch"


@pytest.mark.parametrize("invalid_level", [0, -1])
def test_match_skips_invalid_required_levels(invalid_level):
    skills = [
        {"name": "Python", "required_level": invalid_level},
        {"name": "SQL", "required_level": 2, "demonstrated_level": 2},
    ]
    assert classify_opportunity_match({}, skills) == "strong"


@pytest.mark.parametrize(
    "skills",
    [[], [{"required_level": 0}, {"required_level": -1}]],
)
def test_match_without_valid_required_skills_raises(skills):
    with pytest.raises(ValueError) as error:
        classify_opportunity_match({"degree": True}, skills)
    assert str(error.value) == "No valid required skills to classify."


@pytest.mark.parametrize("earlier_skill", [[], [{"required_level": 2, "demonstrated_level": 0}]])
def test_match_missing_required_level_raises(earlier_skill):
    with pytest.raises(KeyError, match="required_level"):
        classify_opportunity_match({}, earlier_skill + [{"name": "SQL"}])


@pytest.mark.parametrize(
    "sql_values, expected",
    [
        ({"demonstrated_level": 2}, "strong"),
        ({"demonstrated_level": None, "claimed_level": 2}, "good"),
        ({"demonstrated_level": 1}, "stretch"),
    ],
)
def test_match_expected_examples_and_skill_order(sql_values, expected):
    skills = [
        {"name": "Python", "required_level": 2, "demonstrated_level": 2},
        {"name": "SQL", "required_level": 2, **sql_values},
    ]
    assert classify_opportunity_match({}, skills) == expected
    assert classify_opportunity_match({}, list(reversed(skills))) == expected


@pytest.mark.parametrize("filters", [{}, {"degree": True}, {"degree": False}])
def test_match_inputs_are_not_mutated(filters):
    skills = [
        {"name": "Python", "required_level": 0},
        {"name": "SQL", "required_level": 2, "claimed_level": 2},
    ]
    original_filters = deepcopy(filters)
    original_skills = deepcopy(skills)
    classify_opportunity_match(filters, skills)
    assert filters == original_filters
    assert skills == original_skills


@pytest.mark.parametrize(
    "filters, skill_values",
    [
        ({}, {"demonstrated_level": 2}),
        ({}, {"claimed_level": 2}),
        ({}, {"demonstrated_level": 1}),
        ({"degree": False}, {"demonstrated_level": 2}),
    ],
)
def test_match_returns_only_allowed_bands(filters, skill_values):
    result = classify_opportunity_match(
        filters, [{"required_level": 2, **skill_values}]
    )
    assert result in {"strong", "good", "stretch", "not_eligible"}


def test_empty_prerequisites_are_satisfied():
    assert are_prerequisites_satisfied([], {}) is True


@pytest.mark.parametrize(
    "demonstrated_level, expected",
    [(1, True), (2, True), (0, False), (None, False), (-1, False)],
)
def test_prerequisite_demonstrated_level(demonstrated_level, expected):
    prerequisites = [{"skill_name": "Python", "minimum_level": 1}]
    result = are_prerequisites_satisfied(
        prerequisites, {"Python": demonstrated_level}
    )
    assert result is expected
    assert isinstance(result, bool)


def test_demonstrated_below_positive_minimum():
    prerequisites = [{"skill_name": "Python", "minimum_level": 2}]
    assert are_prerequisites_satisfied(prerequisites, {"Python": 1}) is False


@pytest.mark.parametrize("demonstrated_levels", [{}, {"SQL": 3}])
def test_missing_prerequisite_skill_is_not_satisfied(demonstrated_levels):
    prerequisites = [{"skill_name": "Python", "minimum_level": 1}]
    assert are_prerequisites_satisfied(prerequisites, demonstrated_levels) is False


@pytest.mark.parametrize("minimum_level", [0, -1])
def test_nonpositive_prerequisite_minimum_is_skipped(minimum_level):
    prerequisites = [{"skill_name": "Python", "minimum_level": minimum_level}]
    assert are_prerequisites_satisfied(prerequisites, {}) is True


@pytest.mark.parametrize("sql_level, expected", [(1, True), (0, False)])
def test_multiple_prerequisites_and_order(sql_level, expected):
    prerequisites = [
        {"skill_name": "Python", "minimum_level": 1},
        {"skill_name": "SQL", "minimum_level": 1},
    ]
    demonstrated_levels = {"Python": 2, "SQL": sql_level}
    assert are_prerequisites_satisfied(prerequisites, demonstrated_levels) is expected
    assert are_prerequisites_satisfied(
        list(reversed(prerequisites)), demonstrated_levels
    ) is expected


@pytest.mark.parametrize(
    "prerequisite, missing_key",
    [({"skill_name": "Python"}, "minimum_level"),
     ({"minimum_level": 1}, "skill_name")],
)
def test_missing_prerequisite_keys_raise(prerequisite, missing_key):
    with pytest.raises(KeyError) as error:
        are_prerequisites_satisfied([prerequisite], {"Python": 2})
    assert error.value.args == (missing_key,)


@pytest.mark.parametrize("python_level", [None, 0, 2])
def test_prerequisite_inputs_are_not_mutated(python_level):
    prerequisites = [
        {"skill_name": "SQL", "minimum_level": 0},
        {"skill_name": "Python", "minimum_level": 1},
    ]
    demonstrated_levels = {"Python": python_level, "SQL": None}
    original_prerequisites = deepcopy(prerequisites)
    original_levels = deepcopy(demonstrated_levels)
    are_prerequisites_satisfied(prerequisites, demonstrated_levels)
    assert prerequisites == original_prerequisites
    assert demonstrated_levels == original_levels


@pytest.mark.parametrize("demonstrated_level, action_type", [(1, "improve"), (None, "assess")])
def test_next_action_without_prerequisites_is_unchanged(demonstrated_level, action_type):
    skills = [{"name": "SQL", "required_level": 2, "importance": 4,
               "demonstrated_level": demonstrated_level, "assessable": True}]
    expected = {"action_type": action_type, "skill_name": "SQL"}
    assert select_next_action(skills) == expected
    skills[0]["prerequisites"] = []
    assert select_next_action(skills) == expected


@pytest.mark.parametrize("demonstrated_level, action_type", [(1, "improve"), (None, "assess")])
@pytest.mark.parametrize("python_level, allowed", [(1, True), (0, False), (None, False)])
def test_next_action_checks_prerequisite_levels(
    demonstrated_level, action_type, python_level, allowed
):
    skills = [
        {"name": "SQL", "required_level": 2, "importance": 4,
         "demonstrated_level": demonstrated_level, "assessable": True,
         "prerequisites": [{"skill_name": "Python", "minimum_level": 1}]},
        # A zero-importance skill still supplies evidence for prerequisites.
        {"name": "Python", "required_level": 1, "importance": 0,
         "claimed_level": 3, "demonstrated_level": python_level},
    ]
    expected = {"action_type": action_type, "skill_name": "SQL"} if allowed else None
    assert select_next_action(skills) == expected


@pytest.mark.parametrize("demonstrated_level", [1, None])
def test_next_action_missing_prerequisite_blocks_both_buckets(demonstrated_level):
    skills = [{"name": "SQL", "required_level": 2, "importance": 4,
               "demonstrated_level": demonstrated_level, "assessable": True,
               "prerequisites": [{"skill_name": "Python", "minimum_level": 1}]}]
    assert select_next_action(skills) is None


@pytest.mark.parametrize("demonstrated_level, action_type", [(1, "improve"), (None, "assess")])
def test_blocked_highest_priority_skill_yields_next_eligible(demonstrated_level, action_type):
    skills = [
        {"name": "SQL", "required_level": 2, "importance": 100,
         "demonstrated_level": demonstrated_level, "assessable": True,
         "prerequisites": [{"skill_name": "Python", "minimum_level": 1}]},
        {"name": "Statistics", "required_level": 2, "importance": 4,
         "demonstrated_level": demonstrated_level, "assessable": True},
    ]
    assert select_next_action(skills) == {
        "action_type": action_type, "skill_name": "Statistics"
    }


@pytest.mark.parametrize("statistics_level, allowed", [(1, True), (0, False)])
def test_next_action_requires_all_prerequisites(statistics_level, allowed):
    skills = [
        {"name": "SQL", "required_level": 2, "importance": 4,
         "assessable": True, "prerequisites": [
             {"skill_name": "Python", "minimum_level": 1},
             {"skill_name": "Statistics", "minimum_level": 1},
         ]},
        {"name": "Python", "required_level": 1, "importance": 0,
         "demonstrated_level": 2},
        {"name": "Statistics", "required_level": 1, "importance": 0,
         "demonstrated_level": statistics_level},
    ]
    expected = {"action_type": "assess", "skill_name": "SQL"} if allowed else None
    assert select_next_action(skills) == expected


@pytest.mark.parametrize("demonstrated_level, action_type", [(1, "improve"), (None, "assess")])
def test_prerequisite_integration_preserves_order_and_inputs(demonstrated_level, action_type):
    prerequisites = [{"skill_name": "Python", "minimum_level": 1}]
    skills = [
        {"name": "Statistics", "required_level": 2, "importance": 4,
         "demonstrated_level": demonstrated_level, "assessable": True,
         "stable_priority": 2, "prerequisites": deepcopy(prerequisites)},
        {"name": "SQL", "required_level": 2, "importance": 4,
         "demonstrated_level": demonstrated_level, "assessable": True,
         "stable_priority": 1, "prerequisites": deepcopy(prerequisites)},
        {"name": "Python", "required_level": 1, "importance": 0,
         "demonstrated_level": 1},
    ]
    original = deepcopy(skills)
    expected = {"action_type": action_type, "skill_name": "SQL"}
    assert select_next_action(skills) == expected
    assert select_next_action(list(reversed(skills))) == expected
    assert skills == original
