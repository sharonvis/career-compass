"""
SQL Assessment Question Bank
Career Compass - Person 3 Assessment System
"""

SQL_QUESTIONS = [

    # ============================================================
    # FORM A - BEGINNER / FILTERING
    # ============================================================

    {
        "question_id": "SQL-A-001",
        "skill": "SQL",
        "topic": "Filtering",
        "difficulty": "Beginner",
        "type": "SQL",
        "form": "A",
        "prompt": "Find the names of all employees whose salary is greater than 50000.",
        "dataset_id": "employee_dataset_v1",
        "expected_answer": "SELECT name FROM employees WHERE salary > 50000;",
        "points": 1,
    },

    {
        "question_id": "SQL-A-002",
        "skill": "SQL",
        "topic": "Filtering",
        "difficulty": "Beginner",
        "type": "SQL",
        "form": "A",
        "prompt": "Find the names of all employees who work in the Engineering department.",
        "dataset_id": "employee_dataset_v1",
        "expected_answer": "SELECT name FROM employees WHERE department = 'Engineering';",
        "points": 1,
    },

    {
        "question_id": "SQL-A-003",
        "skill": "SQL",
        "topic": "Filtering",
        "difficulty": "Beginner",
        "type": "SQL",
        "form": "A",
        "prompt": "Find the names of employees whose salary is between 40000 and 70000.",
        "dataset_id": "employee_dataset_v1",
        "expected_answer": "SELECT name FROM employees WHERE salary BETWEEN 40000 AND 70000;",
        "points": 1,
    },


    # ============================================================
    # FORM A - INTERMEDIATE / AGGREGATIONS
    # ============================================================

    {
        "question_id": "SQL-A-004",
        "skill": "SQL",
        "topic": "Aggregations",
        "difficulty": "Intermediate",
        "type": "SQL",
        "form": "A",
        "prompt": "Find the average salary of all employees.",
        "dataset_id": "employee_dataset_v1",
        "expected_answer": "SELECT AVG(salary) FROM employees;",
        "points": 1,
    },

    {
        "question_id": "SQL-A-005",
        "skill": "SQL",
        "topic": "Aggregations",
        "difficulty": "Intermediate",
        "type": "SQL",
        "form": "A",
        "prompt": "Find the highest salary among all employees.",
        "dataset_id": "employee_dataset_v1",
        "expected_answer": "SELECT MAX(salary) FROM employees;",
        "points": 1,
    },

    {
        "question_id": "SQL-A-006",
        "skill": "SQL",
        "topic": "Aggregations",
        "difficulty": "Intermediate",
        "type": "SQL",
        "form": "A",
        "prompt": "Count the number of employees in each department.",
        "dataset_id": "employee_dataset_v1",
        "expected_answer": "SELECT department, COUNT(*) FROM employees GROUP BY department;",
        "points": 1,
    },


    # ============================================================
    # FORM A - INTERMEDIATE / JOINS
    # ============================================================

    {
        "question_id": "SQL-A-007",
        "skill": "SQL",
        "topic": "JOINs",
        "difficulty": "Intermediate",
        "type": "SQL",
        "form": "A",
        "prompt": "Display each employee's name along with their department name.",
        "dataset_id": "employee_department_dataset_v1",
        "expected_answer": """
            SELECT e.name, d.department_name
            FROM employees e
            JOIN departments d
            ON e.department_id = d.department_id;
        """,
        "points": 1,
    },

    {
        "question_id": "SQL-A-008",
        "skill": "SQL",
        "topic": "JOINs",
        "difficulty": "Intermediate",
        "type": "SQL",
        "form": "A",
        "prompt": "Find the names of employees who work in the Engineering department using a JOIN.",
        "dataset_id": "employee_department_dataset_v1",
        "expected_answer": """
            SELECT e.name
            FROM employees e
            JOIN departments d
            ON e.department_id = d.department_id
            WHERE d.department_name = 'Engineering';
        """,
        "points": 1,
    },
    # ============================================================
    # FORM B - REASSESSMENT
    # ============================================================

    # ------------------------------------------------------------
    # FORM B - BEGINNER / FILTERING
    # ------------------------------------------------------------

    {
        "question_id": "SQL-B-001",
        "skill": "SQL",
        "topic": "Filtering",
        "difficulty": "Beginner",
        "type": "SQL",
        "form": "B",
        "prompt": "Find the names of all employees whose salary is less than 50000.",
        "dataset_id": "employee_dataset_v1",
        "expected_answer": "SELECT name FROM employees WHERE salary < 50000;",
        "points": 1,
    },

    {
        "question_id": "SQL-B-002",
        "skill": "SQL",
        "topic": "Filtering",
        "difficulty": "Beginner",
        "type": "SQL",
        "form": "B",
        "prompt": "Find the names of all employees who work in the Marketing department.",
        "dataset_id": "employee_dataset_v1",
        "expected_answer": "SELECT name FROM employees WHERE department = 'Marketing';",
        "points": 1,
    },

    {
        "question_id": "SQL-B-003",
        "skill": "SQL",
        "topic": "Filtering",
        "difficulty": "Beginner",
        "type": "SQL",
        "form": "B",
        "prompt": "Find the names of employees whose salary is between 45000 and 65000.",
        "dataset_id": "employee_dataset_v1",
        "expected_answer": "SELECT name FROM employees WHERE salary BETWEEN 45000 AND 65000;",
        "points": 1,
    },

    # ------------------------------------------------------------
    # FORM B - INTERMEDIATE / AGGREGATIONS
    # ------------------------------------------------------------

    {
        "question_id": "SQL-B-004",
        "skill": "SQL",
        "topic": "Aggregations",
        "difficulty": "Intermediate",
        "type": "SQL",
        "form": "B",
        "prompt": "Find the minimum salary among all employees.",
        "dataset_id": "employee_dataset_v1",
        "expected_answer": "SELECT MIN(salary) FROM employees;",
        "points": 1,
    },

    {
        "question_id": "SQL-B-005",
        "skill": "SQL",
        "topic": "Aggregations",
        "difficulty": "Intermediate",
        "type": "SQL",
        "form": "B",
        "prompt": "Find the total salary of all employees.",
        "dataset_id": "employee_dataset_v1",
        "expected_answer": "SELECT SUM(salary) FROM employees;",
        "points": 1,
    },

    {
        "question_id": "SQL-B-006",
        "skill": "SQL",
        "topic": "Aggregations",
        "difficulty": "Intermediate",
        "type": "SQL",
        "form": "B",
        "prompt": "Find the average salary for each department.",
        "dataset_id": "employee_dataset_v1",
        "expected_answer": "SELECT department, AVG(salary) FROM employees GROUP BY department;",
        "points": 1,
    },

    # ------------------------------------------------------------
    # FORM B - INTERMEDIATE / JOINS
    # ------------------------------------------------------------

    {
        "question_id": "SQL-B-007",
        "skill": "SQL",
        "topic": "JOINs",
        "difficulty": "Intermediate",
        "type": "SQL",
        "form": "B",
        "prompt": "Display each employee name along with their department name.",
        "dataset_id": "employee_department_dataset_v1",
        "expected_answer": "SELECT e.name, d.department_name FROM employees e JOIN departments d ON e.department_id = d.department_id;",
        "points": 1,
    },

    {
        "question_id": "SQL-B-008",
        "skill": "SQL",
        "topic": "JOINs",
        "difficulty": "Intermediate",
        "type": "SQL",
        "form": "B",
        "prompt": "Find the names of employees who belong to the HR department.",
        "dataset_id": "employee_department_dataset_v1",
        "expected_answer": "SELECT e.name FROM employees e JOIN departments d ON e.department_id = d.department_id WHERE d.department_name = 'HR';",
        "points": 1,
    },
]