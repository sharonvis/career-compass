import pytest

from services.scoring_service import calculate_skill_credit


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
