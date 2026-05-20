from pydantic import BaseModel, EmailStr


class UserMeResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    status: str
    full_name: str | None = None
    university_group: str | None = None
    class_id: int | None = None
    group_id: int | None = None
    avatar_url: str | None = None


class ClassCreateRequest(BaseModel):
    name: str


class GroupCreateRequest(BaseModel):
    class_id: int
    name: str


class AssignStudentRequest(BaseModel):
    student_id: int
    class_id: int | None = None
    group_id: int | None = None
