"""
SQL Grader
Career Compass - Assessment System

This module:
1. Creates an isolated SQLite database
2. Loads the assessment dataset
3. Runs the student's SQL query
4. Runs the reference SQL query
5. Compares the results
6. Returns a grading result
"""

import sqlite3
import re
QUERY_TIMEOUT_STEPS = 100000

# ============================================================
# 1. CREATE DATABASE TABLES
# ============================================================

def create_database(connection, dataset):
    """
    Create tables and insert the assessment dataset.
    """

    cursor = connection.cursor()

    # Employee dataset
    if "employees" in dataset:

        employees = dataset["employees"]

        if employees and "department" in employees[0]:

            cursor.execute("""
                CREATE TABLE employees (
                    employee_id INTEGER,
                    name TEXT,
                    department TEXT,
                    salary REAL
                )
            """)

            for employee in employees:
                cursor.execute(
                    """
                    INSERT INTO employees
                    (employee_id, name, department, salary)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        employee["employee_id"],
                        employee["name"],
                        employee["department"],
                        employee["salary"],
                    ),
                )

        # Employee + Department dataset
        elif employees and "department_id" in employees[0]:

            cursor.execute("""
                CREATE TABLE employees (
                    employee_id INTEGER,
                    name TEXT,
                    department_id INTEGER,
                    salary REAL
                )
            """)

            for employee in employees:
                cursor.execute(
                    """
                    INSERT INTO employees
                    (employee_id, name, department_id, salary)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        employee["employee_id"],
                        employee["name"],
                        employee["department_id"],
                        employee["salary"],
                    ),
                )

    # Department table
    if "departments" in dataset:

        cursor.execute("""
            CREATE TABLE departments (
                department_id INTEGER,
                department_name TEXT
            )
        """)

        for department in dataset["departments"]:
            cursor.execute(
                """
                INSERT INTO departments
                (department_id, department_name)
                VALUES (?, ?)
                """,
                (
                    department["department_id"],
                    department["department_name"],
                ),
            )

    connection.commit()


# ============================================================
# 2. CHECK SQL SAFETY
# ============================================================

def validate_sql(sql):
    """
    Check whether the submitted SQL is allowed.

    Only SELECT queries are allowed.
    """

    if not sql or not sql.strip():
        return False, "SQL query is empty."

    sql = sql.strip()

    # Remove trailing semicolon for statement checking
    cleaned_sql = sql.rstrip(";").strip()

    # Only one SQL statement is allowed
    if ";" in cleaned_sql:
        return False, "Multiple SQL statements are not allowed."

    # Query must begin with SELECT
    if not re.match(r"^SELECT\b", cleaned_sql, re.IGNORECASE):
        return False, "Only SELECT queries are allowed."

    # Forbidden SQL commands
    forbidden_commands = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "REPLACE",
        "ATTACH",
        "DETACH",
    ]

    for command in forbidden_commands:

        if re.search(r"\b" + command + r"\b", cleaned_sql, re.IGNORECASE):
            return False, f"{command} operations are not allowed."

    return True, "SQL query is valid."

# ============================================================
# 2.5 SQLITE SECURITY AUTHORIZE
# ============================================================

def sqlite_authorizer(action, arg1, arg2, database_name, trigger_name):
    """
    Allow only read-only operations inside the assessment database.
    """

    allowed_actions = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
}

    if action in allowed_actions:
        return sqlite3.SQLITE_OK

    return sqlite3.SQLITE_DENY
# ============================================================
# 3. RUN SQL QUERY
# ============================================================

def execute_query(connection, sql):
    """
    Execute a SELECT query safely.

    Uses:
    - SQLite authorizer
    - Progress handler timeout
    """

    # Enable SQLite read-only authorization
    connection.set_authorizer(sqlite_authorizer)

    # Stop queries that take too long
    def progress_handler():
        return 1

    connection.set_progress_handler(
        progress_handler,
        QUERY_TIMEOUT_STEPS
    )

    cursor = connection.cursor()

    cursor.execute(sql)

    rows = cursor.fetchall()

    rows = [tuple(row) for row in rows]

    # Remove progress handler after execution
    connection.set_progress_handler(None, 0)

    return rows

# ============================================================
# 4. NORMALIZE RESULTS
# ============================================================

def normalize_results(rows):
    """
    Normalize result rows before comparison.

    Column order is preserved.
    Row order is ignored unless the assessment
    explicitly requires ordering.
    """

    normalized = []

    for row in rows:

        normalized_row = []

        for value in row:

            # Normalize floating-point values
            if isinstance(value, float):

                value = round(value, 2)

            normalized_row.append(value)

        normalized.append(tuple(normalized_row))

    # Sort rows so that row order does not matter
    normalized.sort(key=lambda row: str(row))

    return normalized


# ============================================================
# 5. COMPARE RESULTS
# ============================================================

def compare_results(student_rows, reference_rows):
    """
    Compare student's result with reference result.
    """

    student_normalized = normalize_results(student_rows)

    reference_normalized = normalize_results(reference_rows)

    return student_normalized == reference_normalized


# ============================================================
# 6. MAIN GRADING FUNCTION
# ============================================================

def grade_sql(student_sql, reference_sql, dataset):
    """
    Grade a student's SQL query.

    Returns a dictionary containing:
    - correct / incorrect
    - score
    - student result
    - expected result
    - error message
    """

    # --------------------------------------------------------
    # Step 1: Validate SQL
    # --------------------------------------------------------

    valid, message = validate_sql(student_sql)

    if not valid:

        return {
            "correct": False,
            "score": 0,
            "student_result": None,
            "expected_result": None,
            "error": message,
        }

    # --------------------------------------------------------
    # Step 2: Create isolated in-memory database
    # --------------------------------------------------------

    connection = sqlite3.connect(":memory:")

    try:

        # ----------------------------------------------------
        # Step 3: Load dataset
        # ----------------------------------------------------

        create_database(connection, dataset)

        # ----------------------------------------------------
        # Step 4: Run student's query
        # ----------------------------------------------------

        try:

            student_result = execute_query(
                connection,
                student_sql
            )

        except Exception as error:

            return {
                "correct": False,
                "score": 0,
                "student_result": None,
                "expected_result": None,
                "error": f"SQL execution error: {error}",
            }

        # ----------------------------------------------------
        # Step 5: Run reference query
        # ----------------------------------------------------

        try:

            reference_result = execute_query(
                connection,
                reference_sql
            )

        except Exception as error:

            return {
                "correct": False,
                "score": 0,
                "student_result": student_result,
                "expected_result": None,
                "error": f"Reference query error: {error}",
            }

        # ----------------------------------------------------
        # Step 6: Compare results
        # ----------------------------------------------------

        correct = compare_results(
            student_result,
            reference_result
        )

        # ----------------------------------------------------
        # Step 7: Return result
        # ----------------------------------------------------

        if correct:

            return {
                "correct": True,
                "score": 1,
                "student_result": student_result,
                "expected_result": reference_result,
                "error": None,
            }

        else:

            return {
                "correct": False,
                "score": 0,
                "student_result": student_result,
                "expected_result": reference_result,
                "error": "Query result does not match the expected result.",
            }

    finally:

        # Always close the temporary database
        connection.close()