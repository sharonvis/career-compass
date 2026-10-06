UNASSESSED_CREDIT_FACTOR = 0.5


def calculate_assessment_coverage(skills: list[dict]) -> float:
    """Return the importance-weighted fraction of valid skills assessed."""
    assessed_importance = 0
    total_importance = 0
    for skill in skills:
        importance = skill["importance"]
        if importance < 0:
            raise ValueError("importance must not be negative")
        if skill["required_level"] <= 0 or importance == 0:
            continue
        total_importance += importance
        if skill.get("demonstrated_level") is not None:
            assessed_importance += importance
    if total_importance == 0:
        raise ValueError("at least one valid skill is required")
    return assessed_importance / total_importance


def list_confirmed_gaps(skills: list[dict]) -> list[dict]:
    """List assessed positive gaps, ordered by weighted gap and priority."""
    gaps = []
    for skill in skills:
        importance = skill["importance"]
        if importance < 0:
            raise ValueError("importance must not be negative")
        if skill["required_level"] <= 0 or importance == 0:
            continue
        demonstrated_level = skill.get("demonstrated_level")
        gap = calculate_confirmed_skill_gap(skill["required_level"], demonstrated_level)
        if gap is not None and gap > 0:
            result = {
                "skill_name": skill["name"],
                "required_level": skill["required_level"],
                "demonstrated_level": demonstrated_level,
                "gap": gap,
                "importance": importance,
            }
            gaps.append((result, skill.get("stable_priority", float("inf"))))
    gaps.sort(key=lambda item: (-item[0]["importance"] * item[0]["gap"], item[1]))
    return [result for result, priority in gaps]


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


def rank_next_actions(skills: list[dict]) -> list[dict]:
    """Rank eligible improvements, or assessments when no improvements exist."""
    demonstrated_levels = {
        skill["name"]: skill.get("demonstrated_level")
        for skill in skills
    }
    improve_candidates = []
    assess_candidates = []

    for skill in skills:
        name = skill["name"]
        required_level = skill["required_level"]
        importance = skill["importance"]

        if importance < 0:
            raise ValueError("importance must not be negative")
        if importance == 0 or required_level <= 0:
            continue

        if not are_prerequisites_satisfied(
            skill.get("prerequisites", []),
            demonstrated_levels,
        ):
            continue

        demonstrated_level = skill.get("demonstrated_level", None)
        stable_priority = skill.get("stable_priority", float("inf"))

        if demonstrated_level is not None:
            gap = calculate_confirmed_skill_gap(required_level, demonstrated_level)
            if gap >= 1:
                # Larger scores win; negating priority makes lower values win.
                rank = (importance * gap, -stable_priority)
                improve_candidates.append((rank, {"action_type": "improve", "skill_name": name}))
        elif skill.get("assessable", False) is True:
            claimed_level = skill.get("claimed_level", 0)
            unverified_claim = min(max(claimed_level, 0), required_level)
            rank = (importance, unverified_claim, -stable_priority)
            assess_candidates.append((rank, {"action_type": "assess", "skill_name": name}))

    candidates = improve_candidates or assess_candidates
    candidates.sort(key=lambda candidate: candidate[0], reverse=True)
    return [action for rank, action in candidates]


def select_next_action(skills: list[dict]) -> dict | None:
    """Return the first ranked action, preserving the existing selection rules."""
    actions = rank_next_actions(skills)
    return actions[0] if actions else None


def classify_required_skill_statuses(required_skills: list[dict]) -> list[dict]:
    """Describe required skills using demonstrated evidence before claims."""
    statuses = []
    for skill in required_skills:
        required_level = skill["required_level"]
        if required_level <= 0 or skill.get("is_required", True) is False:
            continue
        claimed_level = skill.get("claimed_level", 0)
        demonstrated_level = skill.get("demonstrated_level")
        if demonstrated_level is not None:
            gap = calculate_confirmed_skill_gap(required_level, demonstrated_level)
            status = "gap" if gap > 0 else "met"
        else:
            status = "unverified_ok" if claimed_level >= required_level else "unverified_low"
        statuses.append({
            "skill_name": skill.get("skill_name", skill.get("name")),
            "required_level": required_level,
            "claimed_level": claimed_level,
            "demonstrated_level": demonstrated_level,
            "status": status,
        })
    return statuses


def classify_opportunity_match(
    hard_filter_results: dict[str, bool],
    required_skills: list[dict],
) -> str:
    """Classify eligibility and required skills into an opportunity match band."""
    if any(result is False for result in hard_filter_results.values()):
        return "not_eligible"

    statuses = classify_required_skill_statuses(required_skills)
    if not statuses:
        raise ValueError("No valid required skills to classify.")
    if any(skill["status"] in {"gap", "unverified_low"} for skill in statuses):
        return "stretch"
    if any(skill["status"] == "unverified_ok" for skill in statuses):
        return "good"
    return "strong"


def are_prerequisites_satisfied(
    prerequisites: list[dict],
    demonstrated_levels: dict[str, int | None],
) -> bool:
    """Check whether demonstrated levels meet every meaningful prerequisite."""
    for prerequisite in prerequisites:
        minimum_level = prerequisite["minimum_level"]
        if minimum_level <= 0:
            continue

        skill_name = prerequisite["skill_name"]
        demonstrated_level = demonstrated_levels.get(skill_name)
        if demonstrated_level is None or demonstrated_level < minimum_level:
            return False

    return True
