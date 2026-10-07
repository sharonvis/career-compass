from services.statistics_assessment import (
    grade_answer,
    calculate_topic_scores,
    calculate_statistics_level,
    get_weak_topics,
    evaluate_statistics_assessment,
)


def test_grade_correct_answer():
    question = {
        "correct_answer": "30"
    }

    assert grade_answer(question, "30") is True


def test_grade_wrong_answer():
    question = {
        "correct_answer": "30"
    }

    assert grade_answer(question, "40") is False


def test_calculate_topic_scores():
    results = [
        {
            "question_id": "STAT-A-001",
            "topic": "Mean",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "STAT-A-005",
            "topic": "Mean",
            "difficulty": "Intermediate",
            "correct": False,
        },
        {
            "question_id": "STAT-A-004",
            "topic": "Probability",
            "difficulty": "Beginner",
            "correct": True,
        },
    ]

    scores = calculate_topic_scores(results)

    assert scores["Mean"]["correct"] == 1
    assert scores["Mean"]["total"] == 2
    assert scores["Mean"]["percentage"] == 0.5

    assert scores["Probability"]["correct"] == 1
    assert scores["Probability"]["total"] == 1
    assert scores["Probability"]["percentage"] == 1.0


def test_beginner_level():
    results = [
        {
            "question_id": "STAT-001",
            "topic": "Mean",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "STAT-002",
            "topic": "Median",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "STAT-003",
            "topic": "Mode",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "STAT-004",
            "topic": "Probability",
            "difficulty": "Beginner",
            "correct": False,
        },
    ]

    assert calculate_statistics_level(results) == "Beginner"


def test_intermediate_level():
    results = [
        {
            "question_id": "STAT-001",
            "topic": "Mean",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "STAT-002",
            "topic": "Median",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "STAT-003",
            "topic": "Mode",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "STAT-004",
            "topic": "Probability",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "STAT-005",
            "topic": "Mean",
            "difficulty": "Intermediate",
            "correct": True,
        },
        {
            "question_id": "STAT-006",
            "topic": "Variance",
            "difficulty": "Intermediate",
            "correct": True,
        },
        {
            "question_id": "STAT-007",
            "topic": "Correlation",
            "difficulty": "Intermediate",
            "correct": False,
        },
        {
            "question_id": "STAT-008",
            "topic": "Probability",
            "difficulty": "Intermediate",
            "correct": True,
        },
    ]

    assert calculate_statistics_level(results) == "Intermediate"


def test_get_weak_topics():
    topic_scores = {
        "Mean": {
            "correct": 2,
            "total": 4,
            "percentage": 0.5,
        },
        "Probability": {
            "correct": 4,
            "total": 4,
            "percentage": 1.0,
        },
    }

    weak_topics = get_weak_topics(topic_scores)

    assert len(weak_topics) == 1
    assert weak_topics[0]["topic"] == "Mean"


def test_evaluate_statistics_assessment():
    results = [
        {
            "question_id": "STAT-001",
            "topic": "Mean",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "STAT-002",
            "topic": "Median",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "STAT-003",
            "topic": "Mode",
            "difficulty": "Beginner",
            "correct": True,
        },
        {
            "question_id": "STAT-004",
            "topic": "Probability",
            "difficulty": "Beginner",
            "correct": False,
        },
    ]

    result = evaluate_statistics_assessment(results)

    assert result["estimated_level"] == "Beginner"
    assert "topic_scores" in result
    assert "weak_topics" in result