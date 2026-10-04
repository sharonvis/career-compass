import pytest

from services.scoring_service import calculate_career_readiness, calculate_skill_credit


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
