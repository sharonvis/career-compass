"""Supporting metadata only; evidence never establishes skill verification."""

from datetime import date, datetime
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database.models import Evidence, Skill, User
from services.errors import EvidenceNotFoundError, SkillNotFoundError, UserNotFoundError


MAX_TITLE_LENGTH = 200
MAX_ISSUER_LENGTH = 150
MAX_URL_LENGTH = 2048
UNSET = object()  # Internal partial-update marker; not part of the UI contract.


def _text(value, field, maximum, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    value = " ".join(value.split())
    if required and not value:
        raise ValueError(f"{field} must not be blank")
    if len(value) > maximum:
        raise ValueError(f"{field} must not exceed {maximum} characters")
    return value or None


def _url(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("url must be text")
    value = value.strip()
    if not value:
        return None
    if len(value) > MAX_URL_LENGTH:
        raise ValueError(f"url must not exceed {MAX_URL_LENGTH} characters")
    if any(character.isspace() for character in value):
        raise ValueError("url must not contain internal whitespace")
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc) and bool(parsed.hostname)
    except ValueError as error:
        raise ValueError("url must be an http or https URL with a host") from error
    if not valid:
        raise ValueError("url must be an http or https URL with a host")
    return value


def _date(value, today):
    if value is None:
        return None
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError("evidence_date must be a date object, not a datetime or string")
    today = date.today() if today is None else today
    if value > today:
        raise ValueError("evidence_date must not be in the future")
    return value


def _verify_user(session, user_id):
    if session.get(User, user_id) is None:
        raise UserNotFoundError(f"User {user_id} was not found")


def _verify_skill(session, skill_id):
    if session.get(Skill, skill_id) is None:
        raise SkillNotFoundError(f"Skill {skill_id} was not found")


def _owned_evidence(session, user_id, evidence_id):
    row = session.scalar(select(Evidence).options(joinedload(Evidence.skill))
                         .where(Evidence.id == evidence_id, Evidence.user_id == user_id))
    if row is None:
        raise EvidenceNotFoundError("Evidence was not found")
    return row


def _result(row):
    return dict(evidence_id=row.id, user_id=row.user_id, skill_id=row.skill_id,
                skill_name=row.skill.name, title=row.title, issuer=row.issuer,
                url=row.url, evidence_date=row.evidence_date)


def add_evidence(session: Session, user_id: int, skill_id: int, title: str,
                 issuer: str | None = None, url: str | None = None,
                 evidence_date: date | None = None, *, today: date | None = None) -> dict:
    """Normalize and add metadata, returning the lowest-ID exact duplicate."""
    fields = dict(title=_text(title, "title", MAX_TITLE_LENGTH, required=True),
                  issuer=_text(issuer, "issuer", MAX_ISSUER_LENGTH), url=_url(url),
                  evidence_date=_date(evidence_date, today))
    with session.no_autoflush:
        _verify_user(session, user_id)
        _verify_skill(session, skill_id)
        row = session.scalar(select(Evidence).options(joinedload(Evidence.skill))
                             .filter_by(user_id=user_id, skill_id=skill_id, **fields).order_by(Evidence.id).limit(1))
        if row is None:
            row = Evidence(user_id=user_id, skill_id=skill_id, **fields)
            session.add(row)
    session.flush()
    with session.no_autoflush:
        return _result(row)


def get_evidence(session: Session, user_id: int, evidence_id: int) -> dict:
    with session.no_autoflush:
        return _result(_owned_evidence(session, user_id, evidence_id))


def list_user_evidence(session: Session, user_id: int, skill_id: int | None = None) -> list[dict]:
    """List dated evidence newest first and explicitly place undated rows last."""
    with session.no_autoflush:
        _verify_user(session, user_id)
        query = select(Evidence).options(joinedload(Evidence.skill)).where(Evidence.user_id == user_id)
        if skill_id is not None:
            _verify_skill(session, skill_id)
            query = query.where(Evidence.skill_id == skill_id)
        query = query.order_by(Evidence.evidence_date.is_(None).asc(), Evidence.evidence_date.desc(), Evidence.id.desc())
        return [_result(row) for row in session.scalars(query)]


def update_evidence(session: Session, user_id: int, evidence_id: int, *, title=UNSET,
                    issuer=UNSET, url=UNSET, evidence_date=UNSET, today: date | None = None) -> dict:
    """Validate partial updates before ownership lookup; None clears optionals."""
    fields = {}
    if title is not UNSET:
        fields["title"] = _text(title, "title", MAX_TITLE_LENGTH, required=True)
    if issuer is not UNSET:
        fields["issuer"] = _text(issuer, "issuer", MAX_ISSUER_LENGTH)
    if url is not UNSET:
        fields["url"] = _url(url)
    if evidence_date is not UNSET:
        fields["evidence_date"] = _date(evidence_date, today)
    with session.no_autoflush:
        row = _owned_evidence(session, user_id, evidence_id)
        changed = False
        for field, value in fields.items():
            if getattr(row, field) != value:
                setattr(row, field, value)
                changed = True
    if changed:
        session.flush()
    with session.no_autoflush:
        return _result(row)


def delete_evidence(session: Session, user_id: int, evidence_id: int) -> None:
    with session.no_autoflush:
        row = _owned_evidence(session, user_id, evidence_id)
        session.delete(row)
    session.flush()
