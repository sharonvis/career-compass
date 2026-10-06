"""
Assessment Attempt and History Service

Career Compass - Person 3 Assessment System

This module manages:
- assessment attempts
- attempt status
- submitted answers
- correctness
- errors
- runtime
- topic
- difficulty
- resulting estimated level

This version is framework-independent and uses
in-memory storage.

It can later be connected to the shared database.
"""

from datetime import datetime
import uuid


# ============================================================
# STATUS VALUES
# ============================================================

IN_PROGRESS = "In Progress"
COMPLETED = "Completed"
ABANDONED = "Abandoned"


# ============================================================
# ASSESSMENT HISTORY SERVICE
# ============================================================

class AssessmentHistory:

    def __init__(self):
        """
        Create an empty assessment history.
        """

        self.attempts = {}
        self.answers = {}

    # ========================================================
    # START ATTEMPT
    # ========================================================

    def start_attempt(self, user_id, skill, form):
        """
        Create a new assessment attempt.
        """

        attempt_id = str(uuid.uuid4())

        attempt = {
            "attempt_id": attempt_id,
            "user_id": user_id,
            "skill": skill,
            "form": form,
            "start_time": datetime.now(),
            "completion_time": None,
            "status": IN_PROGRESS,
            "resulting_level": None,
        }

        self.attempts[attempt_id] = attempt

        self.answers[attempt_id] = []

        return attempt

    # ========================================================
    # RECORD ANSWER
    # ========================================================

    def record_answer(
        self,
        attempt_id,
        question_id,
        submitted_answer,
        correct,
        error_message,
        runtime,
        topic,
        difficulty,
    ):
        """
        Save one answer belonging to an assessment attempt.
        """

        if attempt_id not in self.attempts:
            raise ValueError("Assessment attempt not found.")

        attempt = self.attempts[attempt_id]

        if attempt["status"] != IN_PROGRESS:
            raise ValueError(
                "Answers can only be recorded for an "
                "in-progress attempt."
            )

        answer = {
            "question_id": question_id,
            "submitted_answer": submitted_answer,
            "correct": correct,
            "error_message": error_message,
            "runtime": runtime,
            "topic": topic,
            "difficulty": difficulty,
        }

        self.answers[attempt_id].append(answer)

        return answer

    # ========================================================
    # COMPLETE ATTEMPT
    # ========================================================

    def complete_attempt(
        self,
        attempt_id,
        resulting_level,
    ):
        """
        Mark an assessment attempt as completed.
        """

        if attempt_id not in self.attempts:
            raise ValueError("Assessment attempt not found.")

        attempt = self.attempts[attempt_id]

        if attempt["status"] != IN_PROGRESS:
            raise ValueError(
                "Only an in-progress attempt can be completed."
            )

        attempt["status"] = COMPLETED
        attempt["completion_time"] = datetime.now()
        attempt["resulting_level"] = resulting_level

        return attempt

    # ========================================================
    # ABANDON ATTEMPT
    # ========================================================

    def abandon_attempt(self, attempt_id):
        """
        Mark an assessment attempt as abandoned.
        """

        if attempt_id not in self.attempts:
            raise ValueError("Assessment attempt not found.")

        attempt = self.attempts[attempt_id]

        if attempt["status"] != IN_PROGRESS:
            raise ValueError(
                "Only an in-progress attempt can be abandoned."
            )

        attempt["status"] = ABANDONED
        attempt["completion_time"] = datetime.now()

        return attempt

    # ========================================================
    # GET ATTEMPT
    # ========================================================

    def get_attempt(self, attempt_id):
        """
        Return one assessment attempt.
        """

        if attempt_id not in self.attempts:
            raise ValueError("Assessment attempt not found.")

        return self.attempts[attempt_id]

    # ========================================================
    # GET ANSWERS
    # ========================================================

    def get_answers(self, attempt_id):
        """
        Return all answers belonging to an attempt.
        """

        if attempt_id not in self.attempts:
            raise ValueError("Assessment attempt not found.")

        return self.answers[attempt_id]

    # ========================================================
    # GET HISTORY
    # ========================================================

    def get_history(self, user_id):
        """
        Return all assessment attempts for a user.
        """

        history = []

        for attempt in self.attempts.values():

            if attempt["user_id"] == user_id:
                history.append(attempt)

        # Most recent attempts first
        history.sort(
            key=lambda attempt: attempt["start_time"],
            reverse=True,
        )

        return history
    # ========================================================
    # GET NEXT FORM
    # ========================================================

    def get_next_form(self, user_id, skill):
        """
        Determine which assessment form should be used next.

        First attempt:
            Form A

        Second attempt:
            Form B

        Third attempt:
            Form A

        Fourth attempt:
            Form B
        """

        user_attempts = [
            attempt
            for attempt in self.attempts.values()
            if (
                attempt["user_id"] == user_id
                and attempt["skill"] == skill
            )
        ]

        # First attempt
        if len(user_attempts) == 0:
            return "A"

        # Even number of previous attempts → B
        if len(user_attempts) % 2 == 1:
            return "B"

        # Odd number of previous attempts → A
        return "A"