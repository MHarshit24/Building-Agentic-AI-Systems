class Student():
    def __init__(self, name, age, course, marks):
        self.name = name
        self.age = age
        self.course = course
        self.marks = marks
    
    def __str__(self):
        return f"Student(name={self.name}, age={self.age}, course={self.course}, marks={self.marks})"
    
    def __eq__(self, value):
        if isinstance(value, Student):
            return (
                self.name == value.name and 
                self.age == value.age 
                )
        return False

class GraduateStudent(Student):
    def __init__(self, name, age, course, marks, thesis_title):
        super().__init__(name, age, course, marks)
        self.thesis_title = thesis_title
        
    def __str__(self):
        return f"GraduateStudent(name={self.name}, age={self.age}, course={self.course}, marks={self.marks}, thesis_title={self.thesis_title})"