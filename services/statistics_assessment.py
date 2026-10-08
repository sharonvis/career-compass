"""
Statistics Assessment Scoring

Career Compass - Person 3 Assessment System

This module:
- checks Statistics answers
- calculates topic scores
- calculates estimated Statistics level
- identifies weak topics
"""

PASS_THRESHOLD = 0.70


def grade_answer(question, submitted_answer):
    """
    Check whether the submitted answer is correct.

    Returns True or False.
    """
    return submitted_answer == question["correct_answer"]


def calculate_topic_scores(question_results):
    """
    Calculate correct/total/percentage for each topic.

    question_results should contain dictionaries like:

    {
        "question_id": "STAT-A-001",
        "topic": "Mean",
        "difficulty": "Beginner",
        "correct": True
    }
    """

    topics = {}

    for result in question_results:
        topic = result["topic"]

        if topic not in topics:
            topics[topic] = {
                "correct": 0,
                "total": 0
            }

        topics[topic]["total"] += 1

        if result["correct"]:
            topics[topic]["correct"] += 1

    for topic in topics:
        correct = topics[topic]["correct"]
        total = topics[topic]["total"]

        if total == 0:
            percentage = 0
        else:
            percentage = correct / total

        topics[topic]["percentage"] = percentage

    return topics


def calculate_statistics_level(question_results):
    """
    Calculate the student's current estimated Statistics level.

    Rules:
    Beginner:
        >= 70% of Beginner questions

    Intermediate:
        Beginner threshold passed
        AND >= 70% of Intermediate questions

    Advanced:
        Not available in the current lightweight assessment
        because there are no Advanced questions.
    """

    beginner_questions = [
        result
        for result in question_results
        if result["difficulty"] == "Beginner"
    ]

    intermediate_questions = [
        result
        for result in question_results
        if result["difficulty"] == "Intermediate"
    ]

    # Check Beginner
    if not beginner_questions:
        return "Not Demonstrated"

    beginner_correct = sum(
        1 for result in beginner_questions
        if result["correct"]
    )

    beginner_percentage = (
        beginner_correct / len(beginner_questions)
    )

    if beginner_percentage < PASS_THRESHOLD:
        return "Not Demonstrated"

    # Check Intermediate
    if not intermediate_questions:
        return "Beginner"

    intermediate_correct = sum(
        1 for result in intermediate_questions
        if result["correct"]
    )

    intermediate_percentage = (
        intermediate_correct / len(intermediate_questions)
    )

    if intermediate_percentage >= PASS_THRESHOLD:
        return "Intermediate"

    return "Beginner"


def get_weak_topics(topic_scores):
    """
    Return topics where the student scored below 70%.
    """

    weak_topics = []

    for topic, score in topic_scores.items():

        if score["percentage"] < PASS_THRESHOLD:
            weak_topics.append({
                "topic": topic,
                "correct": score["correct"],
                "total": score["total"],
                "percentage": score["percentage"]
            })

    return weak_topics


def evaluate_statistics_assessment(question_results):
    """
    Generate the complete Statistics assessment result.
    """

    topic_scores = calculate_topic_scores(question_results)

    estimated_level = calculate_statistics_level(
        question_results
    )

    weak_topics = get_weak_topics(topic_scores)

    return {
        "estimated_level": estimated_level,
        "topic_scores": topic_scores,
        "weak_topics": weak_topics
    }