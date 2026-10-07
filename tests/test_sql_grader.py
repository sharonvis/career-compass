"""
Basic tests for the Career Compass SQL Grader.
"""

from services.sql_grader import grade_sql
from data.sql_datasets import (
    EMPLOYEES,
    EMPLOYEES_HIDDEN,
    EMPLOYEE_DEPARTMENT_DATASET,
)


# ============================================================
# TEST 1 — CORRECT SQL
# ============================================================

def test_correct_sql():

    student_sql = """
        SELECT name
        FROM employees
        WHERE salary > 50000;
    """

    reference_sql = """
        SELECT name
        FROM employees
        WHERE salary > 50000;
    """

    result = grade_sql(
        student_sql,
        reference_sql,
        {"employees": EMPLOYEES}
    )

    assert result["correct"] is True
    assert result["score"] == 1


# ============================================================
# TEST 2 — WRONG SQL
# ============================================================

def test_wrong_sql():

    student_sql = """
        SELECT name
        FROM employees
        WHERE salary > 70000;
    """

    reference_sql = """
        SELECT name
        FROM employees
        WHERE salary > 50000;
    """

    result = grade_sql(
        student_sql,
        reference_sql,
        {"employees": EMPLOYEES}
    )

    assert result["correct"] is False
    assert result["score"] == 0


# ============================================================
# TEST 3 — EMPTY SQL
# ============================================================

def test_empty_sql():

    result = grade_sql(
        "",
        "SELECT name FROM employees;",
        {"employees": EMPLOYEES}
    )

    assert result["correct"] is False
    assert result["score"] == 0


# ============================================================
# TEST 4 — INSERT SHOULD BE BLOCKED
# ============================================================

def test_insert_blocked():

    student_sql = """
        INSERT INTO employees
        VALUES (10, 'Test', 'Engineering', 50000)
    """

    reference_sql = """
        SELECT name FROM employees;
    """

    result = grade_sql(
        student_sql,
        reference_sql,
        {"employees": EMPLOYEES}
    )

    assert result["correct"] is False
    assert result["score"] == 0


# ============================================================
# TEST 5 — DELETE SHOULD BE BLOCKED
# ============================================================

def test_delete_blocked():

    student_sql = """
        DELETE FROM employees
    """

    reference_sql = """
        SELECT name FROM employees;
    """

    result = grade_sql(
        student_sql,
        reference_sql,
        {"employees": EMPLOYEES}
    )

    assert result["correct"] is False
    assert result["score"] == 0


# ============================================================
# TEST 6 — DROP SHOULD BE BLOCKED
# ============================================================

def test_drop_blocked():

    student_sql = """
        DROP TABLE employees
    """

    reference_sql = """
        SELECT name FROM employees;
    """

    result = grade_sql(
        student_sql,
        reference_sql,
        {"employees": EMPLOYEES}
    )

    assert result["correct"] is False
    assert result["score"] == 0# ============================================================
# TEST 7 — HIDDEN DATASET
# ============================================================

def test_hidden_dataset():

    student_sql = """
        SELECT name
        FROM employees
        WHERE salary > 50000;
    """

    reference_sql = """
        SELECT name
        FROM employees
        WHERE salary > 50000;
    """

    result = grade_sql(
        student_sql,
        reference_sql,
        {"employees": EMPLOYEES_HIDDEN}
    )

    assert result["correct"] is True
    assert result["score"] == 1
    # ============================================================
# TEST 8 — JOIN QUERY
# ============================================================

def test_join_query():

    student_sql = """
        SELECT e.name, d.department_name
        FROM employees e
        JOIN departments d
        ON e.department_id = d.department_id;
    """

    reference_sql = """
        SELECT e.name, d.department_name
        FROM employees e
        JOIN departments d
        ON e.department_id = d.department_id;
    """

    result = grade_sql(
        student_sql,
        reference_sql,
        EMPLOYEE_DEPARTMENT_DATASET
    )

    assert result["correct"] is True
    assert result["score"] == 1
# ============================================================
# TEST 9 — MALFORMED SQL
# ============================================================

def test_malformed_sql():

    student_sql = """
        SELECT name FROM employees WHERE salary >
    """

    reference_sql = """
        SELECT name FROM employees WHERE salary > 50000;
    """

    result = grade_sql(
        student_sql,
        reference_sql,
        {"employees": EMPLOYEES}
    )

    assert result["correct"] is False
    assert result["score"] == 0
    assert result["error"] is not None
    # ============================================================
# TEST 10 — DUPLICATE ROWS MATTER
# ============================================================

def test_duplicate_rows_matter():

    student_sql = """
        SELECT name
        FROM employees
        WHERE department = 'Engineering'
        UNION ALL
        SELECT name
        FROM employees
        WHERE department = 'Engineering';
    """

    reference_sql = """
        SELECT name
        FROM employees
        WHERE department = 'Engineering';
    """

    result = grade_sql(
        student_sql,
        reference_sql,
        {"employees": EMPLOYEES}
    )

    assert result["correct"] is False
    assert result["score"] == 0
    # ============================================================
# TEST 11 — ROW ORDER DOES NOT MATTER
# ============================================================

def test_row_order_does_not_matter():

    student_sql = """
        SELECT name
        FROM employees
        WHERE department = 'Engineering'
        ORDER BY name DESC;
    """

    reference_sql = """
        SELECT name
        FROM employees
        WHERE department = 'Engineering'
        ORDER BY name ASC;
    """

    result = grade_sql(
        student_sql,
        reference_sql,
        {"employees": EMPLOYEES}
    )

    assert result["correct"] is True
    assert result["score"] == 1
    # ============================================================
# TEST 12 — NUMERIC ROUNDING
# ============================================================

# ============================================================
# TEST 12 — NUMERIC ROUNDING
# ============================================================

def test_numeric_rounding():

    student_sql = """
        SELECT AVG(salary) + 0.001
        FROM employees;
    """

    reference_sql = """
        SELECT AVG(salary)
        FROM employees;
    """

    result = grade_sql(
        student_sql,
        reference_sql,
        {"employees": EMPLOYEES}
    )

    assert result["correct"] is True
    assert result["score"] == 1