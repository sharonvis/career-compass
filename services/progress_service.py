"""Explicit, display-only Recent Activity records; callers own transactions."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import ProgressEvent, User
from services.errors import UserNotFoundError


PROGRESS_EVENT_TYPES = (
    "target_career_changed", "assessment_completed", "roadmap_item_completed",
    "opportunity_saved", "application_status_changed", "evidence_added",
)
_TEMPLATES = {
    "target_career_changed": "Target career changed to {subject}.",
    "assessment_completed": "Completed {subject} assessment.",
    "roadmap_item_completed": "Completed roadmap step: {subject}.",
    "opportunity_saved": "Saved {subject}.",
    "application_status_changed": "Application for {subject} moved to {detail}.",
    "evidence_added": "Added evidence: {subject}.",
}


def _text(value, name, maximum):
    if not isinstance(value, str):
        raise ValueError(f"{name} is required and must be text")
    value = " ".join(value.split())
    if not value:
        raise ValueError(f"{name} is required")
    if len(value) > maximum:
        raise ValueError(f"{name} must not exceed {maximum} characters")
    return value


def _verify_user(session, user_id):
    if session.get(User, user_id) is None:
        raise UserNotFoundError(f"User {user_id} was not found")


def _result(row):
    return dict(event_id=row.id, user_id=row.user_id, event_type=row.event_type,
                description=row.description, created_at=row.created_at)


def record_progress_event(session: Session, user_id: int, event_type: str,
                           subject: str | None = None, detail: str | None = None) -> dict:
    """Generate one activity sentence without committing or changing its subject."""
    if event_type not in PROGRESS_EVENT_TYPES:
        raise ValueError("Invalid progress event type")
    subject = _text(subject, "subject", 100)
    if event_type == "application_status_changed":
        detail = _text(detail, "detail", 40)
    elif detail is not None and (not isinstance(detail, str) or " ".join(detail.split())):
        raise ValueError("detail is only allowed for application_status_changed")
    description = _TEMPLATES[event_type].format(subject=subject, detail=detail)
    with session.no_autoflush:
        _verify_user(session, user_id)
        row = ProgressEvent(user_id=user_id, event_type=event_type, description=description)
        session.add(row)
    session.flush()
    return _result(row)


def list_recent_progress_events(session: Session, user_id: int, limit: int = 10) -> list[dict]:
    """List activity newest first; limits are integers from zero through fifty."""
    if type(limit) is not int or not 0 <= limit <= 50:
        raise ValueError("limit must be an integer from 0 to 50")
    with session.no_autoflush:
        _verify_user(session, user_id)
        if limit == 0:
            return []
        query = select(ProgressEvent).where(ProgressEvent.user_id == user_id).order_by(
            ProgressEvent.created_at.desc(), ProgressEvent.id.desc()).limit(limit)
        return [_result(row) for row in session.scalars(query)]
