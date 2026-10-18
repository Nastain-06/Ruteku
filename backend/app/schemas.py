from datetime import date
from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GenerateIn(BaseModel):  # RF-03: preferensi perjalanan dari wizard
    origin: str = Field(min_length=2, max_length=100)
    destination: str = Field(min_length=2, max_length=100)
    start_date: date
    end_date: date
    travelers: int = Field(ge=1, le=50)
    budget: int = Field(gt=0)
    interests: list[str] = []


class SaveIn(BaseModel):
    plan_id: str
    title: str | None = None
