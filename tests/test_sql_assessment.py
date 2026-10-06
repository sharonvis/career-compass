"""
Tests for SQL Assessment Scoring
Career Compass - Person 3 Assessment System
"""

from services.sql_assessment import (
    calculate_topic_scores,
    calculate_sql_level,
    get_weak_topics,
    evaluate_sql_assessment,
)


# ============================================================
# TEST 1 — GOLDEN DEMO RESULT
# ============================================================

def test_golden_demo_level():

    question_results = [

        # Filtering: 3/3
        {
            "question_id": "SQL-A-001",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "SQL-A-002",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "SQL-A-003",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },

        # Aggregations: 2/3
        {
            "question_id": "SQL-A-004",
            "topic": "Aggregations",
            "difficulty": "Intermediate",
            "correct": True,
        },
        {
            "question_id": "SQL-A-005",
            "topic": "Aggregations",
            "difficulty": "Intermediate",
            "correct": True,
        },
        {
            "question_id": "SQL-A-006",
            "topic": "Aggregations",
            "difficulty": "Intermediate",
            "correct": False,
        },

        # JOINs: 0/2
        {
            "question_id": "SQL-A-007",
            "topic": "JOINs",
            "difficulty": "Intermediate",
            "correct": False,
        },
        {
            "question_id": "SQL-A-008",
            "topic": "JOINs",
            "difficulty": "Intermediate",
            "correct": False,
        },
    ]

    result = evaluate_sql_assessment(question_results)

    assert result["estimated_level"] == "Beginner"


# ============================================================
# TEST 2 — TOPIC SCORES
# ============================================================

def test_topic_scores():

    question_results = [

        {
            "question_id": "1",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "2",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "3",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": False,
        },
    ]

    scores = calculate_topic_scores(question_results)

    assert scores["Filtering"]["correct"] == 2
    assert scores["Filtering"]["total"] == 3
    assert scores["Filtering"]["percentage"] == 2 / 3


# ============================================================
# TEST 3 — BEGINNER LEVEL
# ============================================================

def test_beginner_level():

    question_results = [

        {
            "question_id": "1",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "2",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "3",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },
    ]

    level = calculate_sql_level(question_results)

    assert level == "Beginner"


# ============================================================
# TEST 4 — INTERMEDIATE LEVEL
# ============================================================

def test_intermediate_level():

    question_results = [

        # Beginner: 3/3
        {
            "question_id": "1",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "2",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "3",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },

        # Intermediate: 3/3
        {
            "question_id": "4",
            "topic": "Aggregations",
            "difficulty": "Intermediate",
            "correct": True,
        },
        {
            "question_id": "5",
            "topic": "Aggregations",
            "difficulty": "Intermediate",
            "correct": True,
        },
        {
            "question_id": "6",
            "topic": "JOINs",
            "difficulty": "Intermediate",
            "correct": True,
        },
    ]

    level = calculate_sql_level(question_results)

    assert level == "Intermediate"


# ============================================================
# TEST 5 — ADVANCED LEVEL
# ============================================================

def test_advanced_level():

    question_results = [

        # Beginner: 3/3
        {
            "question_id": "1",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "2",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "3",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },

        # Intermediate: 3/3
        {
            "question_id": "4",
            "topic": "Aggregations",
            "difficulty": "Intermediate",
            "correct": True,
        },
        {
            "question_id": "5",
            "topic": "Aggregations",
            "difficulty": "Intermediate",
            "correct": True,
        },
        {
            "question_id": "6",
            "topic": "JOINs",
            "difficulty": "Intermediate",
            "correct": True,
        },

        # Advanced: 2/2
        {
            "question_id": "7",
            "topic": "Advanced SQL",
            "difficulty": "Advanced",
            "correct": True,
        },
        {
            "question_id": "8",
            "topic": "Advanced SQL",
            "difficulty": "Advanced",
            "correct": True,
        },
    ]

    level = calculate_sql_level(question_results)

    assert level == "Advanced"


# ============================================================
# TEST 6 — WEAK TOPICS
# ============================================================

def test_weak_topics():

    question_results = [

        {
            "question_id": "1",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "2",
            "topic": "Filtering",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "3",
            "topic": "JOINs",
            "difficulty": "Intermediate",
            "correct": False,
        },
        {
            "question_id": "4",
            "topic": "JOINs",
            "difficulty": "Intermediate",
            "correct": False,
        },
    ]

    scores = calculate_topic_scores(question_results)

    weak_topics = get_weak_topics(scores)

    weak_topic_names = [
        item["topic"]
        for item in weak_topics
    ]

    assert "JOINs" in weak_topic_names