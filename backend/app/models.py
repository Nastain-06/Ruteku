import uuid
from datetime import date, datetime, timezone
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Destination(Base):
    __tablename__ = "destinations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(50), index=True)
    location: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    price_estimate: Mapped[int] = mapped_column(Integer, default=0)  # harga acuan tiket (IDR)
    lat: Mapped[float] = mapped_column(Float, default=0)
    lng: Mapped[float] = mapped_column(Float, default=0)


class Itinerary(Base):
    __tablename__ = "itineraries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    origin: Mapped[str] = mapped_column(String(100))
    destination: Mapped[str] = mapped_column(String(100))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    travelers: Mapped[int] = mapped_column(Integer)
    budget: Mapped[int] = mapped_column(Integer)
    total_cost: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON)  # prototipe: item itinerary disimpan sebagai JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class UserPreference(Base):  # RF-02: preferensi default pengguna (dipakai untuk mengisi form perencanaan)
    __tablename__ = "user_preferences"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    default_origin: Mapped[str] = mapped_column(String(100), default="")
    default_budget: Mapped[int] = mapped_column(Integer, default=0)
    default_travelers: Mapped[int] = mapped_column(Integer, default=1)
    default_interests: Mapped[list] = mapped_column(JSON, default=list)


class ShareLink(Base):  # RF-14: tautan berbagi dengan masa berlaku (B7: pencarian lewat primary key, bukan scan tabel)
    __tablename__ = "share_links"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    itinerary_id: Mapped[str] = mapped_column(ForeignKey("itineraries.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
