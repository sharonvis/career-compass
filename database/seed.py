"""Validated, repeatable demo catalog. Callers own the transaction."""

from datetime import date, timedelta

from sqlalchemy import select

from database.models import (
    Career, CareerSkillRequirement, Opportunity, OpportunitySkill,
    Skill, SkillPrerequisite,
)


SKILLS = [
    ("Python", "Write clear, reusable Python programs."),
    ("SQL", "Query and manage relational data."),
    ("Statistics", "Apply statistical reasoning to data and uncertainty."),
    ("Machine Learning Fundamentals", "Train and evaluate foundational machine learning models."),
    ("Pandas/Data Handling", "Clean, transform and analyse tabular data with Pandas."),
    ("Git", "Track changes and collaborate using version control."),
    ("Data Structures & Algorithms", "Select data structures and design efficient algorithms."),
    ("Object-Oriented Programming", "Organise reusable software using objects and classes."),
    ("Excel", "Analyse spreadsheet data using formulas and tables."),
    ("Data Visualization", "Communicate insights through clear charts and visualisations."),
]

CAREERS = [
    ("AI/ML Engineer", "Builds, trains and evaluates machine learning models, from preparing data to writing clean, reusable code."),
    ("Software Engineer", "Designs and builds reliable software, with strong fundamentals in programming, data structures and version control."),
    ("Data Analyst", "Turns raw data into clear insight using SQL, spreadsheets, statistics and visualisation."),
]

# career, skill, required_level, importance
CAREER_REQUIREMENTS = [
    ("AI/ML Engineer", "Python", 2, 5),
    ("AI/ML Engineer", "Machine Learning Fundamentals", 2, 5),
    ("AI/ML Engineer", "SQL", 2, 4),
    ("AI/ML Engineer", "Statistics", 2, 4),
    ("AI/ML Engineer", "Pandas/Data Handling", 2, 4),
    ("AI/ML Engineer", "Git", 1, 2),
    ("Software Engineer", "Python", 2, 4),
    ("Software Engineer", "Data Structures & Algorithms", 2, 5),
    ("Software Engineer", "Object-Oriented Programming", 2, 4),
    ("Software Engineer", "Git", 2, 3),
    ("Software Engineer", "SQL", 1, 2),
    ("Data Analyst", "SQL", 2, 5),
    ("Data Analyst", "Excel", 2, 4),
    ("Data Analyst", "Statistics", 2, 4),
    ("Data Analyst", "Data Visualization", 2, 4),
    ("Data Analyst", "Pandas/Data Handling", 2, 3),
    ("Data Analyst", "Python", 1, 3),
]

# skill, prerequisite skill, minimum_level
PREREQUISITES = [
    ("Machine Learning Fundamentals", "Python", 1),
    ("Machine Learning Fundamentals", "Statistics", 1),
    ("Pandas/Data Handling", "Python", 1),
    ("Data Structures & Algorithms", "Python", 1),
    ("Object-Oriented Programming", "Python", 1),
    ("Data Visualization", "Statistics", 1),
]

# Each skill entry is (name, required_level, is_required).
OPPORTUNITIES = [
    dict(title="Machine Learning Intern", company="Nova Labs", location="Chennai", opportunity_type="internship", deadline_days_from_now=30,
         skills=[("Python", 2, True), ("Machine Learning Fundamentals", 1, True), ("Pandas/Data Handling", 1, True), ("Git", 1, False)]),
    dict(title="AI Research Assistant Intern", company="Tessera AI", location="Bengaluru", opportunity_type="internship", deadline_days_from_now=35,
         skills=[("Python", 2, True), ("Statistics", 2, True), ("Machine Learning Fundamentals", 2, True), ("SQL", 1, False)]),
    dict(title="Junior Data Scientist Trainee", company="Vertex Analytics", location="Hyderabad", opportunity_type="entry_level", deadline_days_from_now=40,
         skills=[("Python", 2, True), ("SQL", 2, True), ("Statistics", 2, True), ("Pandas/Data Handling", 2, True), ("Machine Learning Fundamentals", 1, True)]),
    dict(title="Data Engineering Intern", company="DataNest", location="Remote", opportunity_type="internship", deadline_days_from_now=45,
         skills=[("Python", 2, True), ("SQL", 2, True), ("Git", 1, False)]),
    dict(title="Software Development Intern", company="BrightPath Technologies", location="Chennai", opportunity_type="internship", deadline_days_from_now=30,
         skills=[("Python", 2, True), ("Data Structures & Algorithms", 2, True), ("Git", 1, True), ("Object-Oriented Programming", 1, True)]),
    dict(title="Backend Developer Intern", company="Cobalt Ridge Software", location="Pune", opportunity_type="internship", deadline_days_from_now=35,
         skills=[("Python", 2, True), ("Object-Oriented Programming", 2, True), ("SQL", 1, True), ("Git", 2, True)]),
    dict(title="Associate Software Engineer", company="Lumen Works", location="Bengaluru", opportunity_type="entry_level", deadline_days_from_now=40,
         skills=[("Python", 2, True), ("Data Structures & Algorithms", 2, True), ("Object-Oriented Programming", 2, True), ("Git", 1, True), ("SQL", 2, False)]),
    dict(title="Data Analyst Intern", company="Saffron Data Co", location="Chennai", opportunity_type="internship", deadline_days_from_now=30,
         skills=[("SQL", 2, True), ("Excel", 2, True), ("Data Visualization", 1, True), ("Statistics", 1, False)]),
    dict(title="Business Analytics Intern", company="Vertex Analytics", location="Remote", opportunity_type="internship", deadline_days_from_now=35,
         skills=[("Excel", 2, True), ("Data Visualization", 2, True), ("Statistics", 1, True), ("SQL", 1, True)]),
    dict(title="Junior Data Analyst", company="Harbor Light Digital", location="Hyderabad", opportunity_type="entry_level", deadline_days_from_now=45,
         skills=[("SQL", 2, True), ("Python", 1, True), ("Pandas/Data Handling", 2, True), ("Statistics", 2, True), ("Data Visualization", 2, True)]),
]


def validate_seed_constants():
    """Reject invalid references, ranges, duplicate keys and cycles before writes."""
    skill_names = {name for name, description in SKILLS}
    career_names = {name for name, description in CAREERS}
    if len(skill_names) != len(SKILLS) or len(career_names) != len(CAREERS):
        raise ValueError("Duplicate skill or career name")

    def check_skill(name):
        if name not in skill_names:
            raise ValueError(f"Unknown skill reference: {name}")

    def check_level(level):
        if type(level) is not int or not 1 <= level <= 3:
            raise ValueError("Seed level must be an integer from 1 to 3")

    def check_duplicate(seen, key, label):
        if key in seen:
            raise ValueError(f"Duplicate {label}: {key}")
        seen.add(key)

    seen = set()
    for career, skill, level, importance in CAREER_REQUIREMENTS:
        check_skill(skill)
        if career not in career_names:
            raise ValueError(f"Unknown career reference: {career}")
        check_level(level)
        if type(importance) is not int or importance < 1:
            raise ValueError("Importance must be an integer at least 1")
        check_duplicate(seen, (career, skill), "career-skill pair")

    seen = set()
    graph = {name: [] for name in skill_names}
    for skill, prerequisite, level in PREREQUISITES:
        check_skill(skill)
        check_skill(prerequisite)
        check_level(level)
        if skill == prerequisite:
            raise ValueError("Self prerequisite")
        check_duplicate(seen, (skill, prerequisite), "prerequisite pair")
        graph[skill].append(prerequisite)

    visiting, visited = set(), set()

    def visit(skill):
        if skill in visiting:
            raise ValueError("Prerequisite cycle")
        if skill in visited:
            return
        visiting.add(skill)
        for prerequisite in graph[skill]:
            visit(prerequisite)
        visiting.remove(skill)
        visited.add(skill)

    for skill in graph:
        visit(skill)

    seen = set()
    for opportunity in OPPORTUNITIES:
        key = ("seed", opportunity["title"], opportunity["company"])
        check_duplicate(seen, key, "opportunity natural key")
        seen_skills = set()
        for skill, level, required in opportunity["skills"]:
            check_skill(skill)
            check_level(level)
            check_duplicate(seen_skills, skill, "opportunity-skill pair")


def seed_database(session):
    """Insert missing catalog rows and reconcile values without committing."""
    validate_seed_constants()
    summary = {"created": 0, "updated": 0}

    def upsert(model, key, values):
        row = session.scalar(select(model).filter_by(**key))
        if row is None:
            row = model(**key, **values)
            session.add(row)
            session.flush()
            summary["created"] += 1
        else:
            changed = False
            for field, value in values.items():
                if getattr(row, field) != value:
                    setattr(row, field, value)
                    changed = True
            if changed:
                summary["updated"] += 1
        return row

    skills = {name: upsert(Skill, dict(name=name), dict(description=description))
              for name, description in SKILLS}
    careers = {name: upsert(Career, dict(name=name), dict(description=description))
               for name, description in CAREERS}
    for career, skill, level, importance in CAREER_REQUIREMENTS:
        upsert(CareerSkillRequirement,
               dict(career_id=careers[career].id, skill_id=skills[skill].id),
               dict(required_level=level, importance=importance))
    for skill, prerequisite, level in PREREQUISITES:
        upsert(SkillPrerequisite,
               dict(skill_id=skills[skill].id, prerequisite_skill_id=skills[prerequisite].id),
               dict(minimum_level=level))
    for data in OPPORTUNITIES:
        key = dict(source="seed", title=data["title"], company=data["company"])
        values = dict(location=data["location"], opportunity_type=data["opportunity_type"],
                      source_url=None, is_seeded=True)
        existing = session.scalar(select(Opportunity).filter_by(**key))
        if existing is None:
            values["deadline"] = date.today() + timedelta(days=data["deadline_days_from_now"])
        opportunity = upsert(Opportunity, key, values)
        for skill, level, required in data["skills"]:
            upsert(OpportunitySkill,
                   dict(opportunity_id=opportunity.id, skill_id=skills[skill].id),
                   dict(required_level=level, is_required=required))
    session.flush()
    return summary
