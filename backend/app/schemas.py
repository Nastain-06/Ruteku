from datetime import date
from typing import Annotated
from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=120)

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password tidak boleh lebih dari 72 byte")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    email: EmailStr
    token: str = Field(min_length=4, max_length=64)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_bytes(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password tidak boleh lebih dari 72 byte")
        return v


class GenerateIn(BaseModel):  # RF-03: preferensi perjalanan dari wizard
    origin: str = Field(min_length=2, max_length=100)
    destination: str = Field(min_length=2, max_length=100)
    start_date: date
    end_date: date
    travelers: int = Field(ge=1, le=50)
    budget: int = Field(gt=0, le=1_000_000_000)
    interests: list[Annotated[str, Field(max_length=50)]] = Field(default=[], max_length=10)


class SaveIn(BaseModel):
    plan_id: str = Field(min_length=1, max_length=64)
    title: str | None = Field(default=None, max_length=200)
