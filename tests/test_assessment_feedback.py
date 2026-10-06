from services.assessment_feedback import (
    calculate_topic_feedback,
    get_weakest_topic,
    get_next_action,
)


def test_topic_feedback_counts_correct_answers():

    results = [
        {"question_id": "SQL-A-001", "topic": "Filtering", "correct": True},
        {"question_id": "SQL-A-002", "topic": "Filtering", "correct": True},
        {"question_id": "SQL-A-003", "topic": "Filtering", "correct": True},

        {"question_id": "SQL-A-004", "topic": "Aggregations", "correct": True},
        {"question_id": "SQL-A-005", "topic": "Aggregations", "correct": True},
        {"question_id": "SQL-A-006", "topic": "Aggregations", "correct": False},

        {"question_id": "SQL-A-007", "topic": "JOINs", "correct": False},
        {"question_id": "SQL-A-008", "topic": "JOINs", "correct": False},
    ]

    feedback = calculate_topic_feedback(results)

    assert feedback["Filtering"]["correct"] == 3
    assert feedback["Filtering"]["total"] == 3

    assert feedback["Aggregations"]["correct"] == 2
    assert feedback["Aggregations"]["total"] == 3

    assert feedback["JOINs"]["correct"] == 0
    assert feedback["JOINs"]["total"] == 2


def test_topic_scores_are_calculated():

    results = [
        {"question_id": "SQL-A-001", "topic": "Filtering", "correct": True},
        {"question_id": "SQL-A-002", "topic": "Filtering", "correct": False},
    ]

    feedback = calculate_topic_feedback(results)

    assert feedback["Filtering"]["score"] == 50.0


def test_weakest_topic():

    topic_results = {
        "Filtering": {
            "correct": 3,
            "total": 3,
            "score": 100.0,
        },
        "Aggregations": {
            "correct": 2,
            "total": 3,
            "score": 66.67,
        },
        "JOINs": {
            "correct": 0,
            "total": 2,
            "score": 0.0,
        },
    }

    weakest = get_weakest_topic(topic_results)

    assert weakest == "JOINs"


def test_next_action():

    topic_results = {
        "Filtering": {
            "correct": 3,
            "total": 3,
            "score": 100.0,
        },
        "Aggregations": {
            "correct": 2,
            "total": 3,
            "score": 66.67,
        },
        "JOINs": {
            "correct": 0,
            "total": 2,
            "score": 0.0,
        },
    }

    action = get_next_action(topic_results)

    assert action == "Improve SQL JOINs"


def test_empty_results():

    feedback = calculate_topic_feedback([])

    assert feedback == {}
    assert get_weakest_topic(feedback) is None
    assert get_next_action(feedback) is None