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


def _check_pw_bytes(v: str) -> str:
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password tidak boleh lebih dari 72 byte")
    return v


# ---------- RF-10 Edit rencana ----------
class EditItemIn(BaseModel):
    destination_id: int = Field(ge=1)
    time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    note: str = Field(default="", max_length=200)


class EditDayIn(BaseModel):
    items: list[EditItemIn] = Field(default=[], max_length=5)


class EditIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    travelers: int | None = Field(default=None, ge=1, le=50)
    budget: int | None = Field(default=None, gt=0, le=1_000_000_000)
    days: list[EditDayIn] | None = Field(default=None, min_length=1, max_length=14)


# ---------- RF-02 Profil ----------
class ProfileUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    default_origin: str | None = Field(default=None, max_length=100)
    default_budget: int | None = Field(default=None, ge=0, le=1_000_000_000)
    default_travelers: int | None = Field(default=None, ge=1, le=50)
    default_interests: list[Annotated[str, Field(max_length=50)]] | None = Field(default=None, max_length=10)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Nama tidak boleh kosong")
        return v.strip() if v else v


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def validate_new_pw(cls, v: str) -> str:
        return _check_pw_bytes(v)
