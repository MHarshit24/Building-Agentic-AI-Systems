# 🎓 Student Management App

## 📌 Overview

The **Student Management App** is a Python-based application designed to manage student information and performance reports.  

This project demonstrates the evolution of data modeling in Python using:

- Standard Classes (Basic OOP)
- Dataclasses (Cleaner Data Representation)
- Pydantic Models (Validated & Serializable Models)

The application showcases object-oriented principles, structured data modeling, validation, and serialization in a real-world academic scenario.

---

## 🎯 Problem Statement

Design a Python application to:

- Manage student profiles
- Perform grade calculation
- Validate inputs such as age and marks
- Generate structured performance reports
- Serialize validated data into dictionary and JSON formats

---

## 🏗 Project Structure

```
p1-student-management/
│
├── student/
│   ├── models/
│   │   ├── student_base.py
│   │   ├── student_record.py
│   │   ├── student_model.py
│   │   └── __pycache__/
│   ├── main.py
│   └── __init__.py
│
├── pyproject.toml
└── README.md
```


---

# 🧩 Step-by-Step Implementation

---

## 🔹 Step 1: Core Classes (`student_base.py`)

### ✔ Features:
- Base class `Student`
- Derived class `GraduateStudent`
- Custom `__str__()` method for readable display
- Custom `__eq__()` method for object comparison
- Demonstrates inheritance and polymorphism

### Concepts Covered:
- Object-Oriented Programming
- Dunder Methods
- Inheritance
- Method Overriding

---

## 🔹 Step 2: Dataclass Implementation (`student_record.py`)

### ✔ Features:
- Converted student structure into a `@dataclass`
- Automatically generated constructor
- Used `field(init=False)` to exclude enrollment ID from constructor
- Used `__post_init__()` to auto-generate unique enrollment ID
- Implemented grade calculation logic based on marks

### Concepts Covered:
- Decorators
- Dataclasses
- Post-initialization processing
- Cleaner and reusable data modeling

---

## 🔹 Step 3: Pydantic Validation (`student_model.py`)

### ✔ Features:
- Used `BaseModel` from Pydantic
- Automatic type checking
- Field-level validation using `@field_validator`
- Ensured:
  - Name is not empty
  - Age is within valid range
  - Marks are within valid range
  - Guardian number contains only digits
- Clean error handling

### Concepts Covered:
- Data validation
- Type enforcement
- Business rule validation
- Production-ready data models

---

## 🔹 Step 4: Integration & Reporting (`main.py`)

### ✔ Features:
- Instantiated objects from:
  - Basic class
  - Dataclass
  - Pydantic model
- Displayed student details
- Calculated grades
- Serialized validated data using:
  - `model_dump()`
  - `model_dump_json()`

---

# 🚀 How to Run

1. Install dependencies:

```bash
pip install pydantic
```

2. Navigate to the student directory:

```bash
cd student
```

3. Run the application:

```bash
python main.py
```

---

# 📊 Sample Output

```
---- BASIC CLASS ----
Student(name=Rahul, age=21, course=Computer Science, marks=85)

---- GRADUATE STUDENT ----
GraduateStudent(name=Shraddha, age=24, course=Data Science, marks=92, thesis_title=AI in Healthcare)

---- DATACLASS VERSION ----
Name: Amit
Enrollment ID: 550e8400-e29b-41d4-a716-446655440000
Grade: B

---- PYDANTIC MODEL ----
Validated Data:
{'name': 'Neha', 'age': 20, 'marks': 91.0, 'guardian_number': '9876543210'}

JSON:
{"name":"Neha","age":20,"marks":91.0,"guardian_number":"9876543210"}
```

---
