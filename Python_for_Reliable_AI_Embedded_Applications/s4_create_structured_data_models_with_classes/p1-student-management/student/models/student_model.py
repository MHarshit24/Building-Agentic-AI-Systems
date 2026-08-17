from pydantic import BaseModel, field_validator

class StudentModel(BaseModel):
    name: str
    age: int
    marks: float
    guardian_number: str
    
    @field_validator("name")
    def name_must_not_be_empty(cls, value):
        if not value.strip():
            raise ValueError("Name cannot be empty")
        return value

    @field_validator("age")
    def age_must_be_valid(cls, value):
        if value <= 0 or value > 100:
            raise ValueError("Age must be between 1 and 100")
        return value

    @field_validator("marks")
    def marks_must_be_valid(cls, value):
        if value < 0 or value > 100:
            raise ValueError("Marks must be between 0 and 100")
        return value

    @field_validator("guardian_number")
    def guardian_number_must_be_valid(cls, value):
        if not value.isdigit() or len(value) < 8:
            raise ValueError("Guardian number must be a valid numeric string")
        return value