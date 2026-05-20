from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    university_group: str
    class_id: int | None = None
    group_id: int | None = None


class RegisterResponse(BaseModel):
    user_id: int
    status: str


class ApproveUserRequest(BaseModel):
    user_id: int
    status: str


class TeacherLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
