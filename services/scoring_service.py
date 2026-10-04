UNASSESSED_CREDIT_FACTOR = 0.5


def calculate_skill_credit(
    required_level: int,
    claimed_level: int = 0,
    demonstrated_level: int | None = None,
    unassessed_factor: float = UNASSESSED_CREDIT_FACTOR,
) -> float:
    """Calculate credit for levels 0 (Not Known) through 3 (Advanced)."""
    if required_level <= 0:
        raise ValueError("required_level must be greater than 0")

    if demonstrated_level is not None:
        return min(max(demonstrated_level, 0) / required_level, 1.0)

    return unassessed_factor * min(max(claimed_level, 0) / required_level, 1.0)
