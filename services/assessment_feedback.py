"""
Assessment Feedback Service

Calculates topic-level performance from assessment answers
and identifies the weakest topic for improvement.
"""


def calculate_topic_feedback(question_results):
    """
    Calculate correct/total results for each assessment topic.

    Expected input:
    [
        {
            "question_id": "SQL-A-001",
            "topic": "Filtering",
            "correct": True
        },
        ...
    ]

    Returns:
    {
        "Filtering": {
            "correct": 3,
            "total": 3,
            "score": 100.0
        },
        ...
    }
    """

    topic_results = {}

    for result in question_results:
        topic = result["topic"]
        correct = result["correct"]

        if topic not in topic_results:
            topic_results[topic] = {
                "correct": 0,
                "total": 0,
            }

        topic_results[topic]["total"] += 1

        if correct:
            topic_results[topic]["correct"] += 1

    # Calculate percentage
    for topic in topic_results:
        correct = topic_results[topic]["correct"]
        total = topic_results[topic]["total"]

        topic_results[topic]["score"] = round(
            (correct / total) * 100,
            2
        )

    return topic_results


def get_weakest_topic(topic_results):
    """
    Find the topic with the lowest score.

    If two topics have the same score, the topic
    appearing first is selected.
    """

    if not topic_results:
        return None

    weakest_topic = min(
        topic_results,
        key=lambda topic: topic_results[topic]["score"]
    )

    return weakest_topic


def get_next_action(topic_results):
    """
    Convert the weakest topic into a recommended
    improvement action.
    """

    weakest_topic = get_weakest_topic(topic_results)

    if weakest_topic is None:
        return None

    return f"Improve SQL {weakest_topic}"