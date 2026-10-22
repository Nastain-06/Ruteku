from contextlib import asynccontextmanager
from datetime import date as dt_date
import math
import os
import time
import uuid
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from . import cache
from .ai import generate_days
from .config import settings
from .db import Base, SessionLocal, engine, get_db
from .models import Destination, Itinerary, User
from .prices import BASE_HOTEL, BASE_HOTEL_DEFAULT, BASE_TRANSPORT_PP, get_price
from .schemas import GenerateIn, LoginIn, RegisterIn, SaveIn
from .security import DUMMY_HASH, create_token, current_claims, current_user, hash_password, verify_password
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="Ruteku API", version="0.1", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","),
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(SQLAlchemyError)
async def db_exception_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(status_code=503, content={"detail": "Layanan database sedang tidak tersedia, silakan coba beberapa saat lagi"})


@app.exception_handler(redis.RedisError)
async def redis_exception_handler(request: Request, exc: redis.RedisError):
    return JSONResponse(status_code=503, content={"detail": "Layanan cache/sesi sedang tidak tersedia, silakan coba beberapa saat lagi"})


def _escape_like(val: str) -> str:
    return val.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def dest_dict(d: Destination) -> dict:
    return {"id": d.id, "name": d.name, "category": d.category, "location": d.location,
            "description": d.description, "price_estimate": d.price_estimate, "lat": d.lat, "lng": d.lng}


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- RF-01 Autentikasi ----------
@app.post("/auth/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(400, "Email sudah terdaftar")
    db.add(User(email=email, password_hash=hash_password(body.password), full_name=body.full_name))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Email sudah terdaftar")
    return {"message": "Registrasi berhasil, silakan login"}


@app.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    fk = f"login_fail:{email}"
    if int(cache.r.get(fk) or 0) >= 5:  # proteksi brute-force: 5 gagal -> kunci 15 menit
        raise HTTPException(429, "Akun terkunci sementara, coba lagi dalam 15 menit")
    u = db.scalar(select(User).where(User.email == email))
    pw_ok = verify_password(body.password, u.password_hash if u else DUMMY_HASH)
    if not u or not pw_ok:
        cache.r.incr(fk)
        cache.r.expire(fk, 900)
        raise HTTPException(401, "Email atau password salah")
    if u.status != "active":
        raise HTTPException(403, "Akun diblokir")
    cache.r.delete(fk)
    return {"access_token": create_token(u.id), "token_type": "bearer", "full_name": u.full_name}


@app.post("/auth/logout")
def logout(c: dict = Depends(current_claims)):
    ttl = max(int(c["exp"] - time.time()), 1)
    cache.r.set(f"blacklist:{c['jti']}", 1, ex=ttl)  # token masuk blacklist Redis
    return {"message": "Logout berhasil"}


# ---------- RF-05 Pencarian destinasi ----------
@app.get("/destinations")
def search_destinations(
    q: str = Query("", max_length=100),
    category: str = Query("", max_length=50),
    location: str = Query("", max_length=100),
    db: Session = Depends(get_db),
):
    stmt = select(Destination)
    if q:
        eq = f"%{_escape_like(q)}%"
        stmt = stmt.where(Destination.name.ilike(eq, escape="\\") | Destination.description.ilike(eq, escape="\\"))
    if category:
        stmt = stmt.where(Destination.category.ilike(_escape_like(category), escape="\\"))
    if location:
        stmt = stmt.where(Destination.location.ilike(f"%{_escape_like(location)}%", escape="\\"))
    return [dest_dict(d) for d in db.scalars(stmt.order_by(Destination.name))]


# ---------- RF-06 Harga real-time (untuk halaman detail) ----------
@app.get("/prices")
def prices(location: str = Query(..., min_length=2, max_length=100), date: dt_date = Query(...), db: Session = Depends(get_db)):
    dests = db.scalars(select(Destination).where(func.lower(Destination.location) == location.strip().lower())).all()
    if not dests:
        raise HTTPException(404, "Lokasi tidak ditemukan")
    city, day_str = dests[0].location, str(date)
    return {"location": city,
            "hotel_per_night": get_price("hotel", city, day_str, BASE_HOTEL.get(city, BASE_HOTEL_DEFAULT)),
            "tickets": {d.name: get_price("ticket", str(d.id), day_str, d.price_estimate) for d in dests}}


# ---------- RF-03/04/06/08 Generate itinerary ----------
@app.post("/itineraries/generate")
def generate(body: GenerateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.end_date < body.start_date:
        raise HTTPException(400, "Tanggal kepulangan harus setelah tanggal keberangkatan")
    if body.start_date < dt_date.today():
        raise HTTPException(400, "Tanggal keberangkatan tidak boleh di masa lalu")
    if body.origin.strip().lower() == body.destination.strip().lower():
        raise HTTPException(400, "Kota asal dan kota tujuan tidak boleh sama")
    nights = (body.end_date - body.start_date).days
    n_days = nights + 1
    if n_days > 14:
        raise HTTPException(400, "Durasi maksimal 14 hari")
    dests = db.scalars(select(Destination).where(func.lower(Destination.location) == body.destination.strip().lower())).all()
    if not dests:
        raise HTTPException(404, "Tidak ditemukan destinasi yang sesuai, coba destinasi lain")
    by_id = {d.id: d for d in dests}
    city, day0 = dests[0].location, str(body.start_date)

    hotel = get_price("hotel", city, day0, BASE_HOTEL.get(city, BASE_HOTEL_DEFAULT))
    transport = get_price("transport", f"{body.origin.lower()}-{city}", day0, BASE_TRANSPORT_PP)
    days, ai_used = generate_days([dest_dict(d) for d in dests], n_days, body.travelers, body.budget, body.interests)

    tickets_total, missing = 0, []
    for day in days:
        for it in day["items"]:
            d = by_id[it["destination_id"]]
            p = get_price("ticket", str(d.id), day0, d.price_estimate)
            it.update(name=d.name, category=d.category, lat=d.lat, lng=d.lng, ticket_price=p)
            if p["value"] is None:
                missing.append(f"tiket {d.name}")
            else:
                tickets_total += p["value"] * body.travelers

    rooms = math.ceil(body.travelers / 2)
    hotel_total = hotel["value"] * nights * rooms if hotel["value"] is not None and nights else 0
    transport_total = transport["value"] * body.travelers if transport["value"] is not None else 0
    if hotel["value"] is None:
        missing.append("akomodasi")
    if transport["value"] is None:
        missing.append("transportasi")
    total = hotel_total + transport_total + tickets_total  # dihitung sistem, bukan AI

    warnings = ["Harga bersifat estimasi dan dapat berubah sewaktu-waktu sesuai kebijakan penyedia."]
    if len(days) < n_days:
        warnings.append(f"Jadwal hanya mencakup {len(days)} dari {n_days} hari perjalanan karena keterbatasan destinasi.")
    allp = [hotel, transport] + [it["ticket_price"] for dd in days for it in dd["items"]]
    if any(p["stale"] for p in allp):
        warnings.append("Sebagian harga bukan data terbaru karena penyedia harga tidak merespons.")
    if missing:
        warnings.append("Harga tidak tersedia dan tidak masuk total: " + ", ".join(missing))
    if total > body.budget:
        warnings.append(f"Estimasi biaya melebihi anggaran sebesar Rp {total - body.budget:,}".replace(",", "."))

    over_budget = None if (total == 0 and missing) else (total > body.budget)
    plan = {"plan_id": uuid.uuid4().hex, "origin": body.origin, "destination": city,
            "start_date": day0, "end_date": str(body.end_date), "travelers": body.travelers,
            "budget": body.budget, "ai_used": ai_used, "days": days,
            "cost": {"hotel": {"unit": hotel, "nights": nights, "rooms": rooms, "total": hotel_total},
                     "transport": {"unit": transport, "total": transport_total},
                     "tickets": {"total": tickets_total}, "total": total,
                     "over_budget": over_budget, "difference": body.budget - total},
            "warnings": warnings}
    cache.set_json(f"draft:{plan['plan_id']}", {"user_id": user.id, "plan": plan}, 3600)  # draf menunggu disimpan
    return plan


# ---------- RF-09 Simpan, RF-13 Riwayat ----------
@app.post("/itineraries", status_code=201)
def save(body: SaveIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    draft = cache.get_json(f"draft:{body.plan_id}")
    if not draft or draft["user_id"] != user.id:
        raise HTTPException(404, "Draf rencana tidak ditemukan atau sudah kedaluwarsa, silakan generate ulang")
    if draft.get("saved_id"):
        raise HTTPException(409, "Rencana perjalanan ini sudah pernah disimpan")
    p = draft["plan"]
    row = Itinerary(user_id=user.id, title=body.title or f"Perjalanan ke {p['destination']}", origin=p["origin"],
                    destination=p["destination"], start_date=dt_date.fromisoformat(p["start_date"]),
                    end_date=dt_date.fromisoformat(p["end_date"]), travelers=p["travelers"],
                    budget=p["budget"], total_cost=p["cost"]["total"], data=p)
    db.add(row)
    db.commit()
    draft["saved_id"] = row.id
    cache.set_json(f"draft:{body.plan_id}", draft, 3600)
    return {"id": row.id, "title": row.title}


@app.get("/itineraries")
def history(
    limit: int = Query(50, ge=1, le=50),
    offset: int = Query(0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Itinerary)
        .where(Itinerary.user_id == user.id)
        .order_by(Itinerary.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = db.scalars(stmt)
    return [{"id": r.id, "title": r.title, "destination": r.destination, "start_date": str(r.start_date),
             "end_date": str(r.end_date), "total_cost": r.total_cost, "created_at": r.created_at.isoformat()} for r in rows]


@app.get("/itineraries/{iid}")
def detail(iid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(Itinerary, iid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Rencana tidak ditemukan")
    return {"id": r.id, "title": r.title, **r.data}


# ---------- Sajikan Frontend Otomatis di http://localhost:8000 ----------
_frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(_frontend_path):
    app.mount("/", StaticFiles(directory=_frontend_path, html=True), name="frontend")

