"""Persisted SQL/Statistics assessment UI; grading belongs to the service."""
from html import escape

import streamlit as st

from database.db import SessionLocal, session_scope
from services import assessment_service as assessments
from services.user_service import get_user_profile
from ui.components.sidebar import render_sidebar

LEVELS = ("Not Demonstrated", "Beginner", "Intermediate", "Advanced")


def _owned_attempt(session, user_id, attempt_id, skill):
    attempt = assessments.get_attempt(session, attempt_id)
    if attempt["user_id"] != user_id or attempt["skill_name"] != skill:
        raise ValueError("This assessment attempt is not available for your selected skill and profile.")
    return attempt


def _validate_answers(questions, answers):
    for question in questions:
        answer = answers.get(question["question_id"])
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Answer every question before submitting.")
        if question["input_type"] == "multiple_choice" and answer not in question["options"]:
            raise ValueError("Choose one of the provided options for every question.")


st.set_page_config(page_title="Assessment · Career Compass", page_icon="🧭",
                   layout="wide", initial_sidebar_state="expanded")
render_sidebar("My Career")
st.markdown('<h1 class="cc-header-title">Assessment</h1>', unsafe_allow_html=True)
user_id = st.session_state.get("user_id")
if type(user_id) is not int:
    st.info("Complete onboarding before taking an assessment.")
    st.page_link("pages/Onboarding.py", label="Go to Onboarding")
    st.stop()

st.page_link("pages/Dashboard.py", label="Back to Dashboard")
st.page_link("pages/my_career.py", label="Back to My Career")
skill = st.session_state.get("assessment_skill")
supported = {item["skill_name"] for item in assessments.list_supported_assessments()}
if not isinstance(skill, str) or skill not in supported:
    st.info("Choose a supported assessment from Dashboard or My Career.")
    st.stop()

try:
    with SessionLocal() as session:
        get_user_profile(session, user_id)
        stored_id = st.session_state.get("assessment_attempt_id")
        stored = _owned_attempt(session, user_id, stored_id, skill) if stored_id is not None else None
        active = assessments.get_active_assessment_attempt(session, user_id, skill)
        attempt = active or (stored if stored and stored["status"] == "completed" else None)
        history = assessments.get_user_assessment_history(session, user_id, skill)
        questions = assessments.get_assessment_questions(session, user_id, attempt["attempt_id"]) if attempt and attempt["status"] == "in_progress" else []
        recorded = assessments.get_attempt_answers(session, attempt["attempt_id"]) if questions else []
except Exception:
    st.error("Could not load this assessment. Return to My Career and select your assessment again.")
    st.stop()

st.markdown(f'<h2 class="cc-section-title">{escape(skill)}</h2>', unsafe_allow_html=True)
if attempt is not None:
    st.session_state["assessment_attempt_id"] = attempt["attempt_id"]
    st.caption(f"Form {attempt['form_name']} · Attempt #{attempt['attempt_id']}")

if attempt is None:
    st.info("Start when you’re ready. You can return to resume an in-progress attempt.")
    if st.button("Start Assessment", key="assessment_start", type="primary"):
        try:
            with session_scope() as session:
                # Recheck at the write boundary, including starts from another tab.
                started = assessments.get_active_assessment_attempt(session, user_id, skill)
                if started is None:
                    form = assessments.get_next_assessment_form(session, user_id, skill)
                    started = assessments.start_assessment(session, user_id, skill, form)
            st.session_state["assessment_attempt_id"] = started["attempt_id"]
        except Exception:
            st.error("Could not start the assessment. No new attempt was saved. Please try again.")
        else:
            st.rerun()
elif attempt["status"] == "completed":
    st.success(f"Demonstrated level: {LEVELS[attempt['resulting_level']]}")
    st.caption(attempt["completed_at"].strftime("Completed %d %b %Y, %H:%M UTC"))
    st.write("Return to Dashboard or My Career to see your updated readiness and next action.")
    if st.button("Retake Assessment", key="assessment_retake"):
        st.session_state.pop("assessment_attempt_id", None)
        for key in list(st.session_state):
            if key.startswith(f"assessment_{attempt['attempt_id']}_"):
                del st.session_state[key]
        st.rerun()
else:
    attempt_id = attempt["attempt_id"]
    saved_answers = {answer["question_reference"]: answer["submitted_answer"] for answer in recorded}
    st.write("Answer every question, then submit the whole assessment. Your answers are graded by the backend.")
    if questions and questions[0]["input_type"] == "sql":
        st.caption("Write one SELECT query per question using the displayed schema. Hidden grading rows are not shown.")
    answers = {}
    with st.form(f"assessment_form_{attempt_id}"):
        for index, question in enumerate(questions, 1):
            qid = question["question_id"]
            key = f"assessment_{attempt_id}_{qid}"
            st.subheader(f"{index}. {question['prompt']}")
            st.caption(f"{question['topic']} · {question['difficulty']}")
            if qid in saved_answers:
                st.session_state[key] = saved_answers[qid]
            if question["input_type"] == "sql":
                st.caption(f"Dataset: {question['dataset_id']}")
                for table in question["schema"]:
                    st.code(f"{table['table']} ({', '.join(table['columns'])})", language="text")
                answers[qid] = st.text_area("SQL answer", key=key, disabled=qid in saved_answers)
            else:
                answers[qid] = st.radio("Your answer", question["options"], index=None,
                                        key=key, disabled=qid in saved_answers)
        submitted = st.form_submit_button("Submit Assessment", type="primary")
    if submitted:
        try:
            _validate_answers(questions, answers)
            with session_scope() as session:
                persisted = _owned_attempt(session, user_id, attempt_id, skill)
                if persisted["status"] != "in_progress":
                    raise ValueError("This attempt has already been submitted. Reload to see its result.")
                current_questions = assessments.get_assessment_questions(session, user_id, attempt_id)
                if current_questions != questions:
                    raise ValueError("Assessment questions changed. Reload and review your answers.")
                _validate_answers(current_questions, answers)
                previous = {a["question_reference"] for a in assessments.get_attempt_answers(session, attempt_id)}
                for question in current_questions:
                    qid = question["question_id"]
                    if qid not in previous:
                        assessments.record_answer(session, attempt_id, qid, answers[qid])
                assessments.complete_assessment(session, attempt_id)
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.error("Could not submit your assessment. Your new answers were not saved. Please try again.")
        else:
            for key in list(st.session_state):
                if key.startswith(f"assessment_{attempt_id}_"):
                    del st.session_state[key]
            st.rerun()

st.subheader("Completed assessment history")
if not history:
    st.info("No completed attempts yet.")
for entry in history:
    st.write(f"Attempt #{entry['attempt_id']} · Form {entry['form_name']} · {LEVELS[entry['resulting_level']]}")
    st.caption(entry["completed_at"].strftime("%d %b %Y, %H:%M UTC"))
