from dataclasses import dataclass, field
import uuid

@dataclass
class StudentRecord:
    name: str
    age: int
    course: str
    marks: float
    enrollment_id: str = field(init = False)
    
    def __post_init__(self):
        self.enrollment_id = str(uuid.uuid4())
        
    def calculate_grade(self) -> str:
        if self.marks >= 90:
            return "A"
        elif self.marks >= 75:
            return "B"
        elif self.marks >= 60:
            return "C"
        elif self.marks >= 40:
            return "D"
        else:
            return "F"