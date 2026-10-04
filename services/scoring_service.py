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


def calculate_career_readiness(
    skills: list[dict],
    unassessed_factor: float = UNASSESSED_CREDIT_FACTOR,
) -> float:
    """Calculate the importance-weighted average of valid skill credits."""
    total_contribution = 0.0
    total_importance = 0.0

    for skill in skills:
        required_level = skill["required_level"]
        importance = skill["importance"]

        if importance < 0:
            raise ValueError("importance must not be negative")
        if required_level <= 0 or importance == 0:
            continue

        skill_credit = calculate_skill_credit(
            required_level=required_level,
            claimed_level=skill.get("claimed_level", 0),
            demonstrated_level=skill.get("demonstrated_level", None),
            unassessed_factor=unassessed_factor,
        )
        total_contribution += importance * skill_credit
        total_importance += importance

    if total_importance == 0:
        raise ValueError("at least one valid skill is required")

    readiness = total_contribution / total_importance
    return min(max(readiness, 0.0), 1.0)
