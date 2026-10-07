"""Persistent records for Career Compass; derived scores belong in services."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from database.db import Base


class UTCDateTime(TypeDecorator):
    """Store UTC without an offset and restore aware UTC values on reload."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


def utc_now() -> datetime:
    """Return an aware UTC timestamp when a row is inserted or updated."""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True)
    degree: Mapped[str] = mapped_column(String)
    branch: Mapped[str] = mapped_column(String)
    year_of_study: Mapped[int] = mapped_column(Integer)
    target_career_id: Mapped[int | None] = mapped_column(ForeignKey("careers.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    target_career: Mapped[Career | None] = relationship(back_populates="target_users")
    skill_claims: Mapped[list[UserSkillClaim]] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    assessment_attempts: Mapped[list[AssessmentAttempt]] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    applications: Mapped[list[Application]] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    evidence: Mapped[list[Evidence]] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    progress_events: Mapped[list[ProgressEvent]] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    roadmap_completions: Mapped[list[RoadmapCompletion]] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str | None] = mapped_column(Text)

    career_requirements: Mapped[list[CareerSkillRequirement]] = relationship(back_populates="skill", cascade="all, delete-orphan", passive_deletes=True)
    user_claims: Mapped[list[UserSkillClaim]] = relationship(back_populates="skill", cascade="all, delete-orphan", passive_deletes=True)
    assessment_attempts: Mapped[list[AssessmentAttempt]] = relationship(back_populates="skill", cascade="all, delete-orphan", passive_deletes=True)
    opportunity_skills: Mapped[list[OpportunitySkill]] = relationship(back_populates="skill", cascade="all, delete-orphan", passive_deletes=True)
    evidence: Mapped[list[Evidence]] = relationship(back_populates="skill", cascade="all, delete-orphan", passive_deletes=True)
    prerequisites: Mapped[list[SkillPrerequisite]] = relationship(back_populates="skill", foreign_keys="SkillPrerequisite.skill_id", cascade="all, delete-orphan", passive_deletes=True)
    prerequisite_for: Mapped[list[SkillPrerequisite]] = relationship(back_populates="prerequisite_skill", foreign_keys="SkillPrerequisite.prerequisite_skill_id", cascade="all, delete-orphan", passive_deletes=True)


class Career(Base):
    __tablename__ = "careers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str | None] = mapped_column(Text)

    skill_requirements: Mapped[list[CareerSkillRequirement]] = relationship(back_populates="career", cascade="all, delete-orphan", passive_deletes=True)
    target_users: Mapped[list[User]] = relationship(back_populates="target_career", passive_deletes=True)


class CareerSkillRequirement(Base):
    __tablename__ = "career_skill_requirements"
    __table_args__ = (
        CheckConstraint("required_level BETWEEN 0 AND 3", name="ck_career_requirement_level"),
        CheckConstraint("importance >= 1", name="ck_career_requirement_importance"),
        UniqueConstraint("career_id", "skill_id", name="uq_career_skill"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.id", ondelete="CASCADE"))
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), index=True)
    required_level: Mapped[int] = mapped_column(Integer)
    importance: Mapped[int] = mapped_column(Integer)

    career: Mapped[Career] = relationship(back_populates="skill_requirements")
    skill: Mapped[Skill] = relationship(back_populates="career_requirements")


class UserSkillClaim(Base):
    __tablename__ = "user_skill_claims"
    __table_args__ = (
        CheckConstraint("claimed_level BETWEEN 0 AND 3", name="ck_user_claim_level"),
        UniqueConstraint("user_id", "skill_id", name="uq_user_skill_claim"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), index=True)
    claimed_level: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    user: Mapped[User] = relationship(back_populates="skill_claims")
    skill: Mapped[Skill] = relationship(back_populates="user_claims")


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"
    __table_args__ = (
        CheckConstraint("status IN ('in_progress', 'completed', 'abandoned')", name="ck_attempt_status"),
        CheckConstraint("resulting_level IS NULL OR resulting_level BETWEEN 0 AND 3", name="ck_attempt_resulting_level"),
        CheckConstraint(
            "status != 'completed' OR (resulting_level IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_attempt_completed_consistency",
        ),
        Index("ix_assessment_attempts_user_skill", "user_id", "skill_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), index=True)
    form_name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="in_progress")
    # Demonstrated level is derived later from the latest completed attempt.
    resulting_level: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    user: Mapped[User] = relationship(back_populates="assessment_attempts")
    skill: Mapped[Skill] = relationship(back_populates="assessment_attempts")
    answers: Mapped[list[AttemptAnswer]] = relationship(back_populates="attempt", cascade="all, delete-orphan", passive_deletes=True)


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_reference", name="uq_attempt_question"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("assessment_attempts.id", ondelete="CASCADE"), index=True)
    question_reference: Mapped[str] = mapped_column(String)
    submitted_answer: Mapped[str | None] = mapped_column(Text)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    error_message: Mapped[str | None] = mapped_column(Text)
    runtime_ms: Mapped[int | None] = mapped_column(Integer)

    attempt: Mapped[AssessmentAttempt] = relationship(back_populates="answers")


class SkillPrerequisite(Base):
    __tablename__ = "skill_prerequisites"
    __table_args__ = (
        CheckConstraint("minimum_level BETWEEN 0 AND 3", name="ck_prerequisite_level"),
        CheckConstraint("skill_id != prerequisite_skill_id", name="ck_prerequisite_different_skills"),
        UniqueConstraint("skill_id", "prerequisite_skill_id", name="uq_skill_prerequisite"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    prerequisite_skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), index=True)
    minimum_level: Mapped[int] = mapped_column(Integer)

    skill: Mapped[Skill] = relationship(back_populates="prerequisites", foreign_keys=[skill_id])
    prerequisite_skill: Mapped[Skill] = relationship(back_populates="prerequisite_for", foreign_keys=[prerequisite_skill_id])


class RoadmapCompletion(Base):
    __tablename__ = "roadmap_completions"
    __table_args__ = (UniqueConstraint("user_id", "roadmap_item_key", name="uq_user_roadmap_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    roadmap_item_key: Mapped[str] = mapped_column(String)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    user: Mapped[User] = relationship(back_populates="roadmap_completions")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String)
    company: Mapped[str] = mapped_column(String)
    location: Mapped[str | None] = mapped_column(String)
    opportunity_type: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    source_url: Mapped[str | None] = mapped_column(String)
    deadline: Mapped[date | None] = mapped_column(Date)
    is_seeded: Mapped[bool] = mapped_column(Boolean, default=False)

    skills: Mapped[list[OpportunitySkill]] = relationship(back_populates="opportunity", cascade="all, delete-orphan", passive_deletes=True)
    applications: Mapped[list[Application]] = relationship(back_populates="opportunity", passive_deletes="all")


class OpportunitySearchCache(Base):
    __tablename__ = "opportunity_search_cache"

    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    results: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())


class OpportunitySkill(Base):
    __tablename__ = "opportunity_skills"
    __table_args__ = (
        CheckConstraint("required_level BETWEEN 0 AND 3", name="ck_opportunity_skill_level"),
        UniqueConstraint("opportunity_id", "skill_id", name="uq_opportunity_skill"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"))
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), index=True)
    required_level: Mapped[int] = mapped_column(Integer)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)

    opportunity: Mapped[Opportunity] = relationship(back_populates="skills")
    skill: Mapped[Skill] = relationship(back_populates="opportunity_skills")


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint("status IN ('saved', 'applied', 'interview', 'offer', 'rejected', 'withdrawn')", name="ck_application_status"),
        UniqueConstraint("user_id", "opportunity_id", name="uq_user_opportunity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String, default="saved")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    user: Mapped[User] = relationship(back_populates="applications")
    opportunity: Mapped[Opportunity] = relationship(back_populates="applications")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String)
    issuer: Mapped[str | None] = mapped_column(String)
    url: Mapped[str | None] = mapped_column(String)
    evidence_date: Mapped[date | None] = mapped_column(Date)

    user: Mapped[User] = relationship(back_populates="evidence")
    skill: Mapped[Skill] = relationship(back_populates="evidence")


class ProgressEvent(Base):
    __tablename__ = "progress_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    user: Mapped[User] = relationship(back_populates="progress_events")
