"""Non-destructive first-run setup, separate from application business rules."""
from sqlalchemy import inspect, select

from database import db, models, seed


def _catalog_ready(session):
    skills = dict(session.execute(select(models.Skill.id, models.Skill.name)).all())
    careers = dict(session.execute(select(models.Career.id, models.Career.name)).all())
    requirements = {(careers.get(career), skills.get(skill)) for career, skill in
                    session.execute(select(models.CareerSkillRequirement.career_id,
                                           models.CareerSkillRequirement.skill_id))}
    prerequisites = {(skills.get(skill), skills.get(prerequisite)) for skill, prerequisite in
                     session.execute(select(models.SkillPrerequisite.skill_id,
                                            models.SkillPrerequisite.prerequisite_skill_id))}
    return (set(name for name, _ in seed.SKILLS) <= set(skills.values())
            and set(name for name, _ in seed.CAREERS) <= set(careers.values())
            and {(career, skill) for career, skill, _, _ in seed.CAREER_REQUIREMENTS} <= requirements
            and {(skill, prerequisite) for skill, prerequisite, _ in seed.PREREQUISITES} <= prerequisites)


def ensure_local_catalog():
    """Create missing tables and seed only missing catalog data; never reset data."""
    if not db.DATABASE_PATH.parent.exists():
        db.init_db()
    with db.SessionLocal() as session:
        tables = set(inspect(session.get_bind()).get_table_names())
    if not set(db.Base.metadata.tables) <= tables:
        db.init_db()
    with db.SessionLocal() as session:
        ready = _catalog_ready(session)
    if not ready:
        with db.session_scope() as session:
            # Recheck within the transaction before calling the existing upsert path.
            if not _catalog_ready(session):
                seed.seed_database(session)
