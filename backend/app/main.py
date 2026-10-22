from contextlib import asynccontextmanager
from datetime import date as dt_date
import math
import os
import re
import secrets
import socket
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
from .schemas import ForgotPasswordIn, GenerateIn, LoginIn, RegisterIn, ResetPasswordIn, SaveIn
from .security import DUMMY_HASH, create_token, current_claims, current_user, hash_password, verify_password
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="Ruteku API", version="0.1", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/network-info")
def network_info(request: Request):
    lan_ip = "127.0.0.1"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
    except Exception:
        try:
            lan_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            pass
    port = request.url.port or 8000
    return {"lan_ip": lan_ip, "port": port, "mobile_url": f"http://{lan_ip}:{port}"}


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


@app.post("/auth/forgot-password")
def forgot_password(body: ForgotPasswordIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    u = db.scalar(select(User).where(User.email == email))
    if not u:
        raise HTTPException(404, "Email tidak terdaftar")
    code = f"{secrets.randbelow(900000) + 100000}"
    cache.r.set(f"reset_pw:{email}", code, ex=900)  # kode OTP berlaku 15 menit
    return {
        "message": "Kode pemulihan kata sandi berhasil dibuat (berlaku 15 menit)",
        "reset_token": code,
    }


@app.post("/auth/reset-password")
def reset_password(body: ResetPasswordIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    saved_code = cache.r.get(f"reset_pw:{email}")
    if not saved_code or saved_code != body.token.strip():
        raise HTTPException(400, "Kode pemulihan tidak valid atau sudah kedaluwarsa")
    u = db.scalar(select(User).where(User.email == email))
    if not u:
        raise HTTPException(404, "Akun tidak ditemukan")
    u.password_hash = hash_password(body.new_password)
    db.commit()
    cache.r.delete(f"reset_pw:{email}")
    cache.r.delete(f"login_fail:{email}")  # buka kembali kunci brute-force jika sempat terkunci
    return {"message": "Kata sandi berhasil diperbarui, silakan masuk dengan kata sandi baru"}


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


# ---------- RF-11 Penghapusan Rencana Perjalanan (UC-13) ----------
@app.delete("/itineraries/{iid}")
def delete_itinerary(iid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(Itinerary, iid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Rencana tidak ditemukan")
    share_token = (r.data or {}).get("share_token")
    if share_token:
        cache.r.delete(f"share:{share_token}")
    db.delete(r)
    db.commit()
    return {"message": "Rencana perjalanan berhasil dihapus", "id": iid}


# ---------- RF-14 Berbagi Rencana Perjalanan via Tautan Unik (UC-16) ----------
@app.post("/itineraries/{iid}/share")
def share_itinerary(iid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(Itinerary, iid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Rencana tidak ditemukan")
    data = dict(r.data or {})
    share_token = data.get("share_token") or uuid.uuid4().hex
    data["share_token"] = share_token
    r.data = data
    db.commit()
    cache.r.set(f"share:{share_token}", r.id, ex=7 * 86400)
    return {
        "id": r.id,
        "share_token": share_token,
        "share_url": f"/?share={share_token}",
        "message": "Tautan berbagi berhasil dibuat",
    }


@app.get("/shared/{token}")
def get_shared_itinerary(token: str, db: Session = Depends(get_db)):
    if not re.fullmatch(r"[a-f0-9]{16,64}", token):
        raise HTTPException(404, "Rencana perjalanan ini tidak lagi tersedia")
    iid = cache.r.get(f"share:{token}")
    r = db.get(Itinerary, iid) if iid else None
    if not r:
        for row in db.scalars(select(Itinerary)):
            if (row.data or {}).get("share_token") == token:
                r = row
                break
    if not r or (r.data or {}).get("share_token") != token:
        raise HTTPException(404, "Rencana perjalanan ini tidak lagi tersedia")
    clean_data = {k: v for k, v in (r.data or {}).items() if k != "share_token"}
    return {"id": r.id, "title": r.title, "shared": True, **clean_data}


# ---------- Sajikan Frontend Otomatis di http://localhost:8000 ----------
_frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(_frontend_path):
    app.mount("/", StaticFiles(directory=_frontend_path, html=True), name="frontend")

