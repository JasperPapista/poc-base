from pydantic import BaseModel, EmailStr, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LogoutRequest(BaseModel):
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v
