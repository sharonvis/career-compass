"""Manual application tracking. The caller owns every transaction."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from database.models import Application, Opportunity, User
from services.career_service import UserNotFoundError
from services.opportunity_service import OpportunityNotFoundError


APPLICATION_STATUSES = ("saved", "applied", "interview", "offer", "rejected", "withdrawn")
MAX_NOTES_LENGTH = 2000


class ApplicationNotFoundError(LookupError):
    """No application is available to this user for the requested ID."""


class InvalidApplicationStatusError(ValueError):
    """The status is outside the six supported tracking values."""


class ApplicationNotRemovableError(ValueError):
    """Only saved applications can be removed."""


def _verify_user(session, user_id):
    if session.get(User, user_id) is None:
        raise UserNotFoundError(f"User {user_id} was not found")


def _validate_status(status):
    if status not in APPLICATION_STATUSES:
        raise InvalidApplicationStatusError(f"Invalid application status: {status}")


def _normalize_notes(notes):
    if notes is None:
        return None
    if not isinstance(notes, str):
        raise ValueError("notes must be a string or None")
    notes = notes.strip()
    if len(notes) > MAX_NOTES_LENGTH:
        raise ValueError(f"notes must not exceed {MAX_NOTES_LENGTH} characters")
    return notes or None


def _owned_application(session, user_id, application_id):
    with session.no_autoflush:
        row = session.scalar(select(Application).options(joinedload(Application.opportunity))
                             .where(Application.id == application_id, Application.user_id == user_id))
        if row is None:
            raise ApplicationNotFoundError("Application was not found")
        return row


def _result(row, today):
    opportunity = row.opportunity
    today = date.today() if today is None else today
    return dict(application_id=row.id, user_id=row.user_id, opportunity_id=row.opportunity_id,
                status=row.status, notes=row.notes, created_at=row.created_at, updated_at=row.updated_at,
                opportunity=dict(title=opportunity.title, company=opportunity.company,
                                 location=opportunity.location, opportunity_type=opportunity.opportunity_type,
                                 deadline=opportunity.deadline, source=opportunity.source,
                                 source_url=opportunity.source_url, is_seeded=opportunity.is_seeded,
                                 is_expired=opportunity.deadline is not None and opportunity.deadline < today))


def save_opportunity(session: Session, user_id: int, opportunity_id: int,
                     notes: str | None = None, today: date | None = None) -> dict:
    """Save once; later saves retain status and optionally replace notes."""
    with session.no_autoflush:
        _verify_user(session, user_id)
        opportunity = session.get(Opportunity, opportunity_id)
        if opportunity is None:
            raise OpportunityNotFoundError(f"Opportunity {opportunity_id} was not found")
        normalized = _normalize_notes(notes)
        row = session.scalar(select(Application).where(
            Application.user_id == user_id, Application.opportunity_id == opportunity_id))
        if row is None:
            row = Application(user_id=user_id, opportunity_id=opportunity_id, status="saved", notes=normalized)
            session.add(row)
        elif notes is not None and row.notes != normalized:
            row.notes = normalized
    session.flush()
    with session.no_autoflush:
        return _result(row, today)


def get_application(session: Session, user_id: int, application_id: int,
                    today: date | None = None) -> dict:
    """Return only an application owned by the supplied user."""
    with session.no_autoflush:
        return _result(_owned_application(session, user_id, application_id), today)


def list_user_applications(session: Session, user_id: int, status: str | None = None,
                           today: date | None = None) -> list[dict]:
    """List tracked rows newest first, optionally filtering by status."""
    with session.no_autoflush:
        _verify_user(session, user_id)
        if status is not None:
            _validate_status(status)
        query = select(Application).options(joinedload(Application.opportunity)).where(Application.user_id == user_id)
        if status is not None:
            query = query.where(Application.status == status)
        query = query.order_by(Application.updated_at.desc(), Application.id.desc())
        return [_result(row, today) for row in session.scalars(query)]


def update_application_status(session: Session, user_id: int, application_id: int,
                               new_status: str, today: date | None = None) -> dict:
    """Allow any valid status correction; repeating a status is a no-op."""
    _validate_status(new_status)
    row = _owned_application(session, user_id, application_id)
    if row.status != new_status:
        row.status = new_status
        session.flush()
    with session.no_autoflush:
        return _result(row, today)


def update_application_notes(session: Session, user_id: int, application_id: int,
                              notes: str | None, today: date | None = None) -> dict:
    """Normalize or clear notes without forcing timestamps on no-op edits."""
    row = _owned_application(session, user_id, application_id)
    normalized = _normalize_notes(notes)
    if row.notes != normalized:
        row.notes = normalized
        session.flush()
    with session.no_autoflush:
        return _result(row, today)


def remove_saved_application(session: Session, user_id: int, application_id: int) -> None:
    """Remove a saved bookmark; preserve all other application history."""
    row = _owned_application(session, user_id, application_id)
    if row.status != "saved":
        raise ApplicationNotRemovableError("Only saved applications can be removed")
    session.delete(row)
    session.flush()


def get_application_status_counts(session: Session, user_id: int) -> dict[str, int]:
    """Always include every dashboard status in stable order."""
    with session.no_autoflush:
        _verify_user(session, user_id)
        counts = dict.fromkeys(APPLICATION_STATUSES, 0)
        counts.update(session.execute(select(Application.status, func.count(Application.id))
                                      .where(Application.user_id == user_id).group_by(Application.status)).all())
        return counts
