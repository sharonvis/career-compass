"""
Hidden datasets for the Career Compass SQL assessment.

These datasets are used by the SQL grader to execute:
1. The student's SQL query
2. The reference SQL query

Both queries are executed against the same isolated SQLite database.
"""

EMPLOYEES = [
    {
        "employee_id": 1,
        "name": "Arun",
        "department": "Engineering",
        "salary": 65000,
    },
    {
        "employee_id": 2,
        "name": "Priya",
        "department": "HR",
        "salary": 45000,
    },
    {
        "employee_id": 3,
        "name": "Rahul",
        "department": "Engineering",
        "salary": 72000,
    },
    {
        "employee_id": 4,
        "name": "Sneha",
        "department": "Marketing",
        "salary": 52000,
    },
    {
        "employee_id": 5,
        "name": "Karthik",
        "department": "Engineering",
        "salary": 48000,
    },
]


DEPARTMENTS = [
    {
        "department_id": 1,
        "department_name": "Engineering",
    },
    {
        "department_id": 2,
        "department_name": "HR",
    },
    {
        "department_id": 3,
        "department_name": "Marketing",
    },
]


EMPLOYEE_DEPARTMENT_DATASET = {
    "employees": [
        {
            "employee_id": 1,
            "name": "Arun",
            "department_id": 1,
            "salary": 65000,
        },
        {
            "employee_id": 2,
            "name": "Priya",
            "department_id": 2,
            "salary": 45000,
        },
        {
            "employee_id": 3,
            "name": "Rahul",
            "department_id": 1,
            "salary": 72000,
        },
        {
            "employee_id": 4,
            "name": "Sneha",
            "department_id": 3,
            "salary": 52000,
        },
        {
            "employee_id": 5,
            "name": "Karthik",
            "department_id": 1,
            "salary": 48000,
        },
    ],
    "departments": DEPARTMENTS,
}
# ============================================================
# HIDDEN DATASET VARIANT
# ============================================================

EMPLOYEES_HIDDEN = [
    {
        "employee_id": 1,
        "name": "Arun",
        "department": "Engineering",
        "salary": 65000,
    },
    {
        "employee_id": 2,
        "name": "Priya",
        "department": "HR",
        "salary": 58000,
    },
    {
        "employee_id": 3,
        "name": "Rahul",
        "department": "Engineering",
        "salary": 72000,
    },
    {
        "employee_id": 4,
        "name": "Sneha",
        "department": "Marketing",
        "salary": 52000,
    },
    {
        "employee_id": 5,
        "name": "Karthik",
        "department": "Engineering",
        "salary": 48000,
    },
]