from models.student_base import Student, GraduateStudent
from models.student_record import StudentRecord
from models.student_model import StudentModel

def main():
    print("---- BASIC CLASS ----")
    s1 = Student("Rahul", 21, "Computer Science", 85)
    print(s1)

    print("\n---- GRADUATE STUDENT ----")
    g1 = GraduateStudent("Shraddha", 24, "Data Science", 92, "AI in Healthcare")
    print(g1)

    print("\n---- DATACLASS VERSION ----")
    record = StudentRecord("Amit", 22, "IT", 88)
    print(f"Name: {record.name}")
    print(f"Enrollment ID: {record.enrollment_id}")
    print(f"Grade: {record.calculate_grade()}")
    
    print("\n---- PYDANTIC MODEL ----")
    student_model = StudentModel(
        name="Neha",
        age=20,
        marks=91,
        guardian_number="9876543210"
    )
    
    print("Validated Data:")
    print(student_model.model_dump())
    print("JSON:")
    print(student_model.model_dump_json())

if __name__ == "__main__":
    main()
