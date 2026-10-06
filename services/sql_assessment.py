"""
SQL Assessment Scoring
Career Compass - Person 3 Assessment System

This module converts individual SQL question results
into:
- topic scores
- estimated SQL level
- topic feedback
"""

# ============================================================
# LEVEL THRESHOLD
# ============================================================

PASS_THRESHOLD = 0.70


# ============================================================
# CALCULATE TOPIC SCORES
# ============================================================

def calculate_topic_scores(question_results):
    """
    Calculate correct/total/percentage for each topic.

    question_results should contain dictionaries like:

    {
        "question_id": "SQL-A-001",
        "topic": "Filtering",
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

    # Calculate percentages
    for topic in topics:

        correct = topics[topic]["correct"]
        total = topics[topic]["total"]

        if total == 0:
            percentage = 0

        else:
            percentage = correct / total

        topics[topic]["percentage"] = percentage

    return topics


# ============================================================
# CALCULATE LEVEL
# ============================================================

def calculate_sql_level(question_results):
    """
    Calculate the student's current estimated SQL level.

    Rules:

    Beginner:
        >= 70% of Beginner questions

    Intermediate:
        Beginner threshold +
        >= 70% of Intermediate questions

    Advanced:
        Beginner threshold +
        Intermediate threshold +
        >= 70% of Advanced questions
    """

    levels = {
        "Beginner": [],
        "Intermediate": [],
        "Advanced": []
    }

    # Separate questions by difficulty
    for result in question_results:

        difficulty = result["difficulty"]

        if difficulty in levels:
            levels[difficulty].append(result)

    # --------------------------------------------------------
    # Beginner
    # --------------------------------------------------------

    beginner_questions = levels["Beginner"]

    beginner_passed = sum(
        1
        for result in beginner_questions
        if result["correct"]
    )

    if beginner_questions:

        beginner_percentage = (
            beginner_passed / len(beginner_questions)
        )

    else:
        beginner_percentage = 0

    beginner_pass = (
        beginner_percentage >= PASS_THRESHOLD
    )

    if not beginner_pass:
        return "Not Demonstrated"

    # --------------------------------------------------------
    # Intermediate
    # --------------------------------------------------------

    intermediate_questions = levels["Intermediate"]

    intermediate_passed = sum(
        1
        for result in intermediate_questions
        if result["correct"]
    )

    if intermediate_questions:

        intermediate_percentage = (
            intermediate_passed /
            len(intermediate_questions)
        )

    else:
        intermediate_percentage = 0

    intermediate_pass = (
        intermediate_percentage >= PASS_THRESHOLD
    )

    if not intermediate_questions:
        return "Beginner"

    if not intermediate_pass:
        return "Beginner"

    # --------------------------------------------------------
    # Advanced
    # --------------------------------------------------------

    advanced_questions = levels["Advanced"]

    if not advanced_questions:
        return "Intermediate"

    advanced_passed = sum(
        1
        for result in advanced_questions
        if result["correct"]
    )

    advanced_percentage = (
        advanced_passed /
        len(advanced_questions)
    )

    advanced_pass = (
        advanced_percentage >= PASS_THRESHOLD
    )

    if advanced_pass:
        return "Advanced"

    return "Intermediate"


# ============================================================
# FIND WEAK TOPICS
# ============================================================

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


# ============================================================
# GENERATE ASSESSMENT RESULT
# ============================================================

def evaluate_sql_assessment(question_results):
    """
    Generate the complete SQL assessment result.
    """

    topic_scores = calculate_topic_scores(
        question_results
    )

    estimated_level = calculate_sql_level(
        question_results
    )

    weak_topics = get_weak_topics(
        topic_scores
    )

    return {
        "estimated_level": estimated_level,
        "topic_scores": topic_scores,
        "weak_topics": weak_topics
    }