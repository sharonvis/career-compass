"""User profiles and onboarding writes; callers own transaction boundaries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Career, CareerSkillRequirement, Skill, User, UserSkillClaim
from services.career_service import CareerNotFoundError, UserNotFoundError
from services.errors import SkillNotFoundError


def _normalize_email(email):
    return email.strip().lower()


def _get_user(session, user_id):
    user = session.get(User, user_id)
    if user is None:
        raise UserNotFoundError(f"User {user_id} was not found")
    return user


def _profile(session, user):
    # Look up by the current FK so a previously loaded relationship cannot be stale.
    career = session.get(Career, user.target_career_id) if user.target_career_id is not None else None
    return dict(user_id=user.id, name=user.name, email=user.email, degree=user.degree,
                branch=user.branch, year_of_study=user.year_of_study,
                target_career_id=user.target_career_id,
                target_career_name=career.name if career is not None else None)


def create_user(session: Session, name: str, email: str, degree: str, branch: str,
                year_of_study: int) -> dict:
    """Create a profile with a normalized email and no selected career."""
    name = name.strip()
    email = _normalize_email(email)
    if not name:
        raise ValueError("name must not be blank")
    if not email:
        raise ValueError("email must not be blank")
    with session.no_autoflush:
        if session.scalar(select(User.id).where(User.email == email)) is not None:
            raise ValueError(f"A user with email {email} already exists")
        user = User(name=name, email=email, degree=degree, branch=branch,
                    year_of_study=year_of_study, target_career_id=None)
        session.add(user)
    session.flush()
    with session.no_autoflush:
        return _profile(session, user)


def get_user_by_email(session: Session, email: str) -> dict | None:
    """Read a normalized-email profile, or None when absent."""
    with session.no_autoflush:
        user = session.scalar(select(User).where(User.email == _normalize_email(email)))
        return _profile(session, user) if user is not None else None


def get_user_profile(session: Session, user_id: int) -> dict:
    with session.no_autoflush:
        return _profile(session, _get_user(session, user_id))


def list_careers(session: Session) -> list[dict]:
    """Return the catalog in career ID order, without readiness calculations."""
    with session.no_autoflush:
        return [dict(career_id=career.id, name=career.name, description=career.description)
                for career in session.scalars(select(Career).order_by(Career.id))]


def set_target_career(session: Session, user_id: int, career_id: int) -> dict:
    """Select an existing career without resetting any accumulated user state."""
    with session.no_autoflush:
        user = _get_user(session, user_id)
        career = session.get(Career, career_id) if career_id is not None else None
        if career is None:
            raise CareerNotFoundError(f"Career {career_id} was not found")
        previous = user.target_career_id
        changed = previous != career_id
        if changed:
            user.target_career_id = career_id
    session.flush()
    return dict(user_id=user_id, previous_career_id=previous, target_career_id=career_id,
                career_name=career.name, changed=changed)


def set_skill_claim(session: Session, user_id: int, skill_id: int, claimed_level: int) -> dict:
    """Upsert a self-reported level; assessment evidence remains unchanged."""
    if type(claimed_level) is not int or not 0 <= claimed_level <= 3:
        raise ValueError("claimed_level must be an integer from 0 to 3")
    with session.no_autoflush:
        _get_user(session, user_id)
        skill = session.get(Skill, skill_id)
        if skill is None:
            raise SkillNotFoundError(f"Skill {skill_id} was not found")
        claim = session.scalar(select(UserSkillClaim).where(
            UserSkillClaim.user_id == user_id, UserSkillClaim.skill_id == skill_id))
        if claim is None:
            session.add(UserSkillClaim(user_id=user_id, skill_id=skill_id, claimed_level=claimed_level))
        elif claim.claimed_level != claimed_level:
            claim.claimed_level = claimed_level
    session.flush()
    return dict(user_id=user_id, skill_id=skill_id, skill_name=skill.name, claimed_level=claimed_level)


def list_career_skills(session: Session, career_id: int) -> list[dict]:
    """Read active catalog requirements without user state, scoring or writes."""
    with session.no_autoflush:
        if session.get(Career, career_id) is None:
            raise CareerNotFoundError(f"Career {career_id} was not found")
        rows = session.execute(
            select(Skill.id, Skill.name, CareerSkillRequirement.required_level,
                   CareerSkillRequirement.importance)
            .join(CareerSkillRequirement, CareerSkillRequirement.skill_id == Skill.id)
            .where(CareerSkillRequirement.career_id == career_id,
                   CareerSkillRequirement.required_level > 0,
                   CareerSkillRequirement.importance > 0)
            .order_by(Skill.id)
        )
        return [dict(skill_id=row.id, name=row.name, required_level=row.required_level,
                     importance=row.importance) for row in rows]
