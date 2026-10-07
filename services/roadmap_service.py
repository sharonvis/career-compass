"""Deterministic learning steps; completion is never assessment evidence."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import AssessmentAttempt, RoadmapCompletion, User
from services.career_service import UserNotFoundError, get_user_career_summary
from services.scoring_service import calculate_confirmed_skill_gap, rank_next_actions


def _item(skill, action_type, key, *, completed=False, reassess=False):
    current = skill["claimed_level"] if action_type == "learn" else skill["demonstrated_level"]
    gap = skill["required_level"] - current if action_type == "learn" else skill["gap"]
    if reassess:
        title = f"Reassess {skill['name']}"
        reason = "Improvement completed; reassess to establish a new demonstrated level."
    elif action_type == "learn":
        title = f"Learn {skill['name']}"
        reason = "Self-reported level is below the requirement; this is unverified learning guidance."
    elif action_type == "improve":
        title = f"Improve {skill['name']}"
        reason = "The latest completed assessment shows a confirmed skill gap."
    else:
        title = f"Assess {skill['name']}"
        reason = "No completed assessment establishes a demonstrated level yet."
    return dict(item_key=key, position=0, action_type=action_type,
                skill_id=skill["skill_id"], skill_name=skill["name"], title=title,
                reason=reason, required_level=skill["required_level"], current_level=current,
                gap=gap, status="completed" if completed else "up_next",
                prerequisites_met=skill["prerequisites_met"])


def _rank_scoring_category(skills, action_type):
    """Reuse scoring order; summary prerequisite flags determine roadmap locks."""
    candidates = []
    for skill in skills:
        assessed = skill["demonstrated_level"] is not None
        include = assessed if action_type == "improve" else not assessed
        # Keep every demonstrated level available in the scoring lookup. Clear
        # prerequisites only to order locked steps as well as actionable ones.
        candidates.append(dict(skill, importance=skill["importance"] if include else 0,
                               prerequisites=[]))
    return rank_next_actions(candidates)


def get_user_roadmap(session: Session, user_id: int, career_id: int, limit: int = 5) -> list[dict]:
    """Return active steps and relevant completed history, without database writes."""
    if type(limit) is not int or limit < 1:
        raise ValueError("limit must be a positive integer")
    with session.no_autoflush:
        summary = get_user_career_summary(session, user_id, career_id)
        skills = summary["skills"]
        by_name = {skill["name"]: skill for skill in skills}
        by_id = {skill["skill_id"]: skill for skill in skills}
        completions = {row.roadmap_item_key: row for row in session.scalars(
            select(RoadmapCompletion).where(RoadmapCompletion.user_id == user_id)
            .order_by(RoadmapCompletion.id)
        )}
        groups = []
        history = []
        used_history = set()
        for action_type in ("improve", "assess"):
            for action in _rank_scoring_category(skills, action_type):
                skill = by_name[action["skill_name"]]
                key = f"{action_type}:{skill['skill_id']}"
                if action_type == "improve":
                    key += f":{skill['latest_attempt_id']}"
                completion = completions.get(key)
                if action_type == "improve" and completion is not None and completion.completed:
                    previous = _item(skill, "improve", key, completed=True)
                    active = _item(skill, "assess",
                                   f"reassess:{skill['skill_id']}:{skill['latest_attempt_id']}", reassess=True)
                    groups.append([previous, active])
                    used_history.add(key)
                else:
                    groups.append([_item(skill, action_type, key)])

        learning = [skill for skill in skills if not skill["assessable"]
                    and skill["demonstrated_level"] is None
                    and skill["claimed_level"] < skill["required_level"]]
        learning.sort(key=lambda skill: (-skill["importance"],
                                        -(skill["required_level"] - skill["claimed_level"]),
                                        skill["stable_priority"]))
        for skill in learning:
            key = f"learn:{skill['skill_id']}"
            completion = completions.get(key)
            item = _item(skill, "learn", key,
                         completed=completion is not None and completion.completed)
            if item["status"] == "completed":
                history.append(item)
            else:
                groups.append([item])

        # Put actionable steps before locks so a small limit cannot hide current.
        groups = ([group for group in groups if group[-1]["prerequisites_met"]]
                  + [group for group in groups if not group[-1]["prerequisites_met"]])
        if not groups:
            return []
        result = []
        has_current = False
        for group in groups[:limit]:
            active = group[-1]
            if not active["prerequisites_met"]:
                active["status"] = "locked"
            elif not has_current:
                active["status"] = "current"
                has_current = True
            result.extend(group)
        for group in groups[limit:]:
            history.extend(group[:-1])  # Completion history does not consume the active limit.

        # Older improve completions stay visible only for relevant, valid attempts.
        for key, completion in completions.items():
            if not completion.completed or key in used_history:
                continue
            parts = key.split(":")
            if len(parts) != 3 or parts[0] != "improve":
                continue
            try:
                skill_id, attempt_id = int(parts[1]), int(parts[2])
            except ValueError:
                continue
            skill = by_id.get(skill_id)
            if skill is None or attempt_id == skill["latest_attempt_id"]:
                continue
            attempt = session.get(AssessmentAttempt, attempt_id)
            if (attempt is None or attempt.user_id != user_id or attempt.skill_id != skill_id
                    or attempt.status != "completed"):
                continue
            historical = dict(skill, demonstrated_level=attempt.resulting_level,
                              gap=calculate_confirmed_skill_gap(skill["required_level"], attempt.resulting_level))
            history.append(_item(historical, "improve", key, completed=True))
        result.extend(history)
        for position, item in enumerate(result, 1):
            item["position"] = position
        return result


def _completion_row(session, user_id, item_key):
    if not isinstance(item_key, str) or not item_key.startswith(("improve:", "learn:")):
        raise ValueError("Only improve: and learn: items can be manually completed")
    with session.no_autoflush:
        if session.get(User, user_id) is None:
            raise UserNotFoundError(f"User {user_id} was not found")
        row = session.scalar(select(RoadmapCompletion).where(
            RoadmapCompletion.user_id == user_id, RoadmapCompletion.roadmap_item_key == item_key))
        if row is None:
            row = next((row for row in session.new if isinstance(row, RoadmapCompletion)
                        and row.user_id == user_id and row.roadmap_item_key == item_key), None)
        if row is None:
            row = RoadmapCompletion(user_id=user_id, roadmap_item_key=item_key)
            session.add(row)
        return row


def mark_roadmap_item_completed(session: Session, user_id: int, item_key: str,
                                completed_at=None) -> RoadmapCompletion:
    """Mark a learning step complete; the caller commits or rolls back."""
    row = _completion_row(session, user_id, item_key)
    row.completed = True
    row.completed_at = completed_at if completed_at is not None else datetime.now(timezone.utc)
    return row


def mark_roadmap_item_incomplete(session: Session, user_id: int, item_key: str) -> RoadmapCompletion:
    """Clear manual completion without changing any assessment evidence."""
    row = _completion_row(session, user_id, item_key)
    row.completed = False
    row.completed_at = None
    return row
