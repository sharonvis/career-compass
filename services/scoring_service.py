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


def calculate_confirmed_skill_gap(
    required_level: int,
    demonstrated_level: int | None = None,
) -> int | None:
    """Return the assessed skill gap, or None when the skill is unassessed."""
    if required_level <= 0:
        raise ValueError("required_level must be greater than 0.")

    if demonstrated_level is None:
        return None

    demonstrated_level = max(demonstrated_level, 0)
    return max(required_level - demonstrated_level, 0)


def select_next_action(skills: list[dict]) -> dict | None:
    """Choose a confirmed gap to improve, or an unassessed skill to assess."""
    best_improve = None
    best_improve_rank = None
    best_assess = None
    best_assess_rank = None

    for skill in skills:
        name = skill["name"]
        required_level = skill["required_level"]
        importance = skill["importance"]

        if importance < 0:
            raise ValueError("importance must not be negative")
        if importance == 0 or required_level <= 0:
            continue

        demonstrated_level = skill.get("demonstrated_level", None)
        stable_priority = skill.get("stable_priority", float("inf"))

        if demonstrated_level is not None:
            gap = calculate_confirmed_skill_gap(required_level, demonstrated_level)
            if gap >= 1:
                # Larger scores win; negating priority makes lower values win.
                rank = (importance * gap, -stable_priority)
                if best_improve_rank is None or rank > best_improve_rank:
                    best_improve_rank = rank
                    best_improve = {"action_type": "improve", "skill_name": name}
        elif skill.get("assessable", False) is True:
            claimed_level = skill.get("claimed_level", 0)
            unverified_claim = min(max(claimed_level, 0), required_level)
            rank = (importance, unverified_claim, -stable_priority)
            if best_assess_rank is None or rank > best_assess_rank:
                best_assess_rank = rank
                best_assess = {"action_type": "assess", "skill_name": name}

    if best_improve is not None:
        return best_improve
    return best_assess
