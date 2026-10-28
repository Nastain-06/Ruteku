from contextlib import asynccontextmanager
from datetime import date as dt_date, datetime, timedelta, timezone
import ipaddress
import math
import os
import re
import secrets
import socket
import time
import uuid
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import redis
from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from . import cache
from .ai import _sanitize_interests, generate_days
from .config import settings
from .db import Base, SessionLocal, engine, get_db
from .models import Destination, Itinerary, ShareLink, User, UserPreference
from .prices import BASE_HOTEL, BASE_HOTEL_DEFAULT, BASE_TRANSPORT_PP, get_price
from .schemas import (
    ChangePasswordIn,
    EditIn,
    ForgotPasswordIn,
    GenerateIn,
    LoginIn,
    ProfileUpdateIn,
    RegisterIn,
    ResetPasswordIn,
    SaveIn,
)
from .security import (
    DUMMY_HASH,
    create_token,
    current_claims,
    current_user,
    hash_password,
    revoke_user_sessions,
    verify_password,
)
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="Ruteku API", version="0.2", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Limit", "X-Offset"],
)


@app.exception_handler(SQLAlchemyError)
async def db_exception_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(status_code=503, content={"detail": "Layanan database sedang tidak tersedia, silakan coba beberapa saat lagi"})


@app.exception_handler(redis.RedisError)
async def redis_exception_handler(request: Request, exc: redis.RedisError):
    return JSONResponse(status_code=503, content={"detail": "Layanan cache/sesi sedang tidak tersedia, silakan coba beberapa saat lagi"})


def _escape_like(val: str) -> str:
    return val.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _client_ip(request: Request) -> str:
    """B3: Hanya percayai X-Forwarded-For jika peer berasal dari trusted_proxies dan format IP valid."""
    peer = request.client.host if request.client else "unknown"
    if peer in settings.trusted_proxy_set:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            candidate = xff.split(",")[0].strip()
            try:
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                pass
    return peer


def _clear_login_failures(email: str) -> None:
    """B1: Hapus seluruh counter gagal login untuk email ini di semua IP."""
    cache.r.delete(f"login_fail:{email}")
    try:
        for k in cache.r.keys(f"login_fail:*:{email}"):
            cache.r.delete(k)
    except Exception:
        pass


def dest_dict(d: Destination) -> dict:
    return {"id": d.id, "name": d.name, "category": d.category, "location": d.location,
            "description": d.description, "price_estimate": d.price_estimate, "lat": d.lat, "lng": d.lng}


# ---------- RF-20 Kalkulasi Jarak (Haversine) & Estimasi Waktu Tempuh ----------
def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    if not (lat1 or lng1) or not (lat2 or lng2):
        return 0.0
    r_earth = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    straight_km = 2 * r_earth * math.asin(min(1.0, math.sqrt(a)))
    return round(straight_km * 1.25, 1)  # faktor kelokan jalan raya ~1.25x jarak garis lurus


def _estimate_travel_min(distance_km: float) -> int:
    if distance_km <= 0:
        return 0
    # kecepatan rata-rata wisata dalam kota/antar objek ~35 km/jam + 5 menit parkir/persiapan
    return max(5, int(round((distance_km / 35.0) * 60)) + 5)


def _enrich_route_metrics(days: list[dict]) -> dict:
    """Tambahkan jarak & estimasi waktu tempuh antar destinasi berurutan per hari (RF-20)."""
    total_km = 0.0
    total_min = 0
    for day in days:
        day_km = 0.0
        day_min = 0
        prev_lat, prev_lng = None, None
        for idx, it in enumerate(day.get("items", [])):
            lat, lng = it.get("lat", 0.0), it.get("lng", 0.0)
            if idx == 0 or prev_lat is None:
                it["distance_from_prev_km"] = 0.0
                it["travel_time_min"] = 0
            else:
                dkm = _haversine_km(prev_lat, prev_lng, lat, lng)
                tmin = _estimate_travel_min(dkm)
                it["distance_from_prev_km"] = dkm
                it["travel_time_min"] = tmin
                day_km = round(day_km + dkm, 1)
                day_min += tmin
            prev_lat, prev_lng = lat, lng
        day["day_distance_km"] = round(day_km, 1)
        day["day_travel_time_min"] = day_min
        total_km = round(total_km + day_km, 1)
        total_min += day_min
    return {"total_distance_km": round(total_km, 1), "total_travel_time_min": total_min}


def _build_cost_and_warnings(
    origin: str,
    city: str,
    day0: str,
    nights: int,
    n_days: int,
    travelers: int,
    budget: int,
    days: list[dict],
    by_id: dict[int, Destination],
) -> tuple[dict, list[str], dict]:
    """Hitung biaya deterministik (RF-06/RF-08) & metrik rute (RF-20)."""
    hotel = get_price("hotel", city, day0, BASE_HOTEL.get(city, BASE_HOTEL_DEFAULT))
    transport = get_price("transport", f"{origin.lower()}-{city}", day0, BASE_TRANSPORT_PP)

    tickets_total, missing = 0, []
    for day in days:
        for it in day["items"]:
            d = by_id[it["destination_id"]]
            p = get_price("ticket", str(d.id), day0, d.price_estimate)
            it.update(name=d.name, category=d.category, lat=d.lat, lng=d.lng, ticket_price=p)
            if p["value"] is None:
                missing.append(f"tiket {d.name}")
            else:
                tickets_total += p["value"] * travelers

    route_summary = _enrich_route_metrics(days)

    rooms = math.ceil(travelers / 2)
    hotel_total = hotel["value"] * nights * rooms if hotel["value"] is not None and nights else 0
    transport_total = transport["value"] * travelers if transport["value"] is not None else 0
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
    if total > budget:
        warnings.append(f"Estimasi biaya melebihi anggaran sebesar Rp {total - budget:,}".replace(",", "."))

    over_budget = None if (total == 0 and missing) else (total > budget)
    cost = {
        "hotel": {"unit": hotel, "nights": nights, "rooms": rooms, "total": hotel_total},
        "transport": {"unit": transport, "total": transport_total},
        "tickets": {"total": tickets_total},
        "total": total,
        "over_budget": over_budget,
        "difference": budget - total,
    }
    return cost, warnings, route_summary


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
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    rk = f"reg_rate:{ip}"
    if int(cache.r.get(rk) or 0) >= 10:
        raise HTTPException(429, "Terlalu banyak permintaan registrasi, silakan coba lagi nanti")
    # B4: hitung setiap percobaan registrasi (termasuk yang gagal karena duplikat) agar tidak bisa di-spam
    cache.r.incr(rk)
    cache.r.expire(rk, 60)
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
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower()
    ip = _client_ip(request)
    fk = f"login_fail:{ip}:{email}"
    if int(cache.r.get(fk) or 0) >= 5:  # NFR-07: proteksi brute-force per IP+email (5 gagal -> kunci 15 menit)
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
    # B4: jangan hapus reg_rate:{ip} saat login agar rate-limit registrasi tidak bisa di-reset lewat login
    return {"access_token": create_token(u.id), "token_type": "bearer", "full_name": u.full_name}


@app.post("/auth/logout")
def logout(c: dict = Depends(current_claims)):
    ttl = max(int(c["exp"] - time.time()), 1)
    cache.r.set(f"blacklist:{c['jti']}", 1, ex=ttl)  # token masuk blacklist Redis
    return {"message": "Logout berhasil"}


@app.post("/auth/forgot-password")
def forgot_password(body: ForgotPasswordIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower()
    ip = _client_ip(request)
    frk = f"forgot_rate:{ip}:{email}"
    if int(cache.r.get(frk) or 0) >= 5:
        raise HTTPException(429, "Terlalu banyak permintaan kode pemulihan, silakan coba lagi nanti")
    cache.r.incr(frk)
    cache.r.expire(frk, 900)

    u = db.scalar(select(User).where(User.email == email))
    if not u:
        if not settings.demo_mode:
            # B5: di mode produksi, samarkan respons agar tidak membocorkan apakah email terdaftar
            return {"message": "Jika email terdaftar, kode pemulihan telah dikirim (berlaku 15 menit)"}
        raise HTTPException(404, "Email tidak terdaftar")
    code = f"{secrets.randbelow(900000) + 100000}"
    cache.r.set(f"reset_pw:{email}", code, ex=900)  # kode OTP berlaku 15 menit
    cache.r.delete(f"reset_fail:{email}")
    res = {"message": "Kode pemulihan kata sandi berhasil dibuat (berlaku 15 menit)"}
    if settings.demo_mode:
        res["reset_token"] = code
    return res


@app.post("/auth/reset-password")
def reset_password(body: ResetPasswordIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    fail_key = f"reset_fail:{email}"
    # B2: batasi percobaan tebak OTP maksimal 5 kali
    if int(cache.r.get(fail_key) or 0) >= 5:
        cache.r.delete(f"reset_pw:{email}")
        raise HTTPException(429, "Terlalu banyak percobaan kode OTP, silakan minta kode pemulihan baru")

    saved_code = cache.r.get(f"reset_pw:{email}")
    if not saved_code or saved_code != body.token.strip():
        cache.r.incr(fail_key)
        cache.r.expire(fail_key, 900)
        if int(cache.r.get(fail_key) or 0) >= 5:
            cache.r.delete(f"reset_pw:{email}")
            raise HTTPException(429, "Terlalu banyak percobaan kode OTP, silakan minta kode pemulihan baru")
        raise HTTPException(400, "Kode pemulihan tidak valid atau sudah kedaluwarsa")
    u = db.scalar(select(User).where(User.email == email))
    if not u:
        raise HTTPException(404, "Akun tidak ditemukan")
    u.password_hash = hash_password(body.new_password)
    db.commit()
    cache.r.delete(f"reset_pw:{email}")
    cache.r.delete(fail_key)
    _clear_login_failures(email)  # B1: hapus semua login_fail:{ip}:{email}
    revoke_user_sessions(u.id)    # cabut seluruh sesi lama sebelum reset sandi
    return {"message": "Kata sandi berhasil diperbarui, silakan masuk dengan kata sandi baru"}


# ---------- RF-02 Manajemen Profil & Preferensi Default ----------
def _pref_dict(pref: UserPreference | None) -> dict:
    if not pref:
        return {"default_origin": "Samarinda", "default_budget": 9_000_000, "default_travelers": 2, "default_interests": ["alam", "budaya"]}
    return {
        "default_origin": pref.default_origin or "Samarinda",
        "default_budget": pref.default_budget if pref.default_budget > 0 else 9_000_000,
        "default_travelers": pref.default_travelers if pref.default_travelers >= 1 else 2,
        "default_interests": pref.default_interests if pref.default_interests is not None else ["alam", "budaya"],
    }


@app.get("/auth/me")
def get_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    pref = db.get(UserPreference, user.id)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "status": user.status,
        "preferences": _pref_dict(pref),
    }


@app.patch("/auth/me")
def update_profile(body: ProfileUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.full_name is not None:
        user.full_name = body.full_name
    pref = db.get(UserPreference, user.id)
    if not pref:
        pref = UserPreference(
            user_id=user.id,
            default_origin="Samarinda",
            default_budget=9_000_000,
            default_travelers=2,
            default_interests=["alam", "budaya"],
        )
        db.add(pref)
    if body.default_origin is not None:
        clean_origin = body.default_origin.strip()
        if len(clean_origin) < 2:
            raise HTTPException(400, "Kota asal default minimal 2 karakter")
        pref.default_origin = clean_origin
    if body.default_budget is not None:
        pref.default_budget = body.default_budget
    if body.default_travelers is not None:
        pref.default_travelers = body.default_travelers
    if body.default_interests is not None:
        pref.default_interests = [x.lower() for x in _sanitize_interests(body.default_interests)]
    db.commit()
    return {
        "message": "Profil dan preferensi berhasil diperbarui",
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "preferences": _pref_dict(pref),
    }


@app.post("/auth/change-password")
def change_password(body: ChangePasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Kata sandi saat ini salah")
    if body.current_password == body.new_password:
        raise HTTPException(400, "Kata sandi baru tidak boleh sama dengan kata sandi lama")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    revoke_user_sessions(user.id)
    time.sleep(0.002)
    new_tok = create_token(user.id)
    return {"message": "Kata sandi berhasil diubah", "access_token": new_tok}


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


# ---------- RF-03/04/06/08/20 Generate itinerary ----------
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

    days, ai_used = generate_days([dest_dict(d) for d in dests], n_days, body.travelers, body.budget, body.interests)
    cost, warnings, route_summary = _build_cost_and_warnings(
        body.origin, city, day0, nights, n_days, body.travelers, body.budget, days, by_id
    )

    plan = {"plan_id": uuid.uuid4().hex, "origin": body.origin, "destination": city,
            "start_date": day0, "end_date": str(body.end_date), "travelers": body.travelers,
            "budget": body.budget, "ai_used": ai_used, "days": days,
            "route_summary": route_summary,
            "cost": cost,
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
    response: Response,
    limit: int = Query(50, ge=1, le=50),
    offset: int = Query(0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    total_count = db.scalar(select(func.count()).select_from(Itinerary).where(Itinerary.user_id == user.id)) or 0
    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)
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
    pdata = dict(r.data or {})
    if "days" in pdata and "route_summary" not in pdata:
        pdata["route_summary"] = _enrich_route_metrics(pdata["days"])
    return {"id": r.id, "title": r.title, **pdata}


# ---------- RF-20 Endpoint Metrik Rute & Waktu Tempuh ----------
@app.get("/itineraries/{iid}/route-metrics")
def get_route_metrics(iid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(Itinerary, iid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Rencana tidak ditemukan")
    pdata = dict(r.data or {})
    days = [dict(d, items=[dict(it) for it in d.get("items", [])]) for d in pdata.get("days", [])]
    summary = _enrich_route_metrics(days)
    return {
        "id": r.id,
        "destination": r.destination,
        "route_summary": summary,
        "days": [
            {
                "day": d["day"],
                "day_distance_km": d.get("day_distance_km", 0.0),
                "day_travel_time_min": d.get("day_travel_time_min", 0),
                "items": [
                    {
                        "destination_id": it.get("destination_id"),
                        "name": it.get("name"),
                        "time": it.get("time"),
                        "lat": it.get("lat"),
                        "lng": it.get("lng"),
                        "distance_from_prev_km": it.get("distance_from_prev_km", 0.0),
                        "travel_time_min": it.get("travel_time_min", 0),
                    }
                    for it in d.get("items", [])
                ],
            }
            for d in days
        ],
    }


# ---------- RF-10 Pengeditan Rencana Perjalanan ----------
@app.patch("/itineraries/{iid}")
@app.put("/itineraries/{iid}")
def edit_itinerary(iid: str, body: EditIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(Itinerary, iid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Rencana tidak ditemukan")
    if body.title is None and body.travelers is None and body.budget is None and body.days is None:
        raise HTTPException(400, "Tidak ada perubahan yang dikirim")

    pdata = dict(r.data or {})
    city = r.destination
    dests = db.scalars(select(Destination).where(func.lower(Destination.location) == city.strip().lower())).all()
    by_id = {d.id: d for d in dests}

    new_title = body.title.strip() if body.title is not None else r.title
    if not new_title:
        raise HTTPException(400, "Judul rencana tidak boleh kosong")
    new_travelers = body.travelers if body.travelers is not None else r.travelers
    new_budget = body.budget if body.budget is not None else r.budget

    nights = (r.end_date - r.start_date).days
    n_days = nights + 1

    if body.days is not None:
        if len(body.days) > n_days:
            raise HTTPException(400, f"Jumlah hari pada jadwal ({len(body.days)}) melebihi durasi perjalanan ({n_days} hari)")
        new_days = []
        total_items = 0
        for idx, d_in in enumerate(body.days, start=1):
            seen_in_day = set()
            day_items = []
            for it_in in d_in.items:
                if it_in.destination_id not in by_id:
                    raise HTTPException(400, f"Destinasi ID {it_in.destination_id} tidak valid untuk kota {city}")
                if it_in.destination_id in seen_in_day:
                    raise HTTPException(400, f"Destinasi ID {it_in.destination_id} duplikat pada hari yang sama")
                seen_in_day.add(it_in.destination_id)
                day_items.append({
                    "destination_id": it_in.destination_id,
                    "time": it_in.time,
                    "note": it_in.note.strip(),
                })
                total_items += 1
            if day_items:
                new_days.append({"day": len(new_days) + 1, "items": day_items})
        if total_items == 0:
            raise HTTPException(400, "Jadwal perjalanan harus memiliki minimal 1 destinasi")
    else:
        new_days = [
            {
                "day": d["day"],
                "items": [
                    {"destination_id": it["destination_id"], "time": it.get("time", "09:00"), "note": it.get("note", "")}
                    for it in d.get("items", [])
                    if it.get("destination_id") in by_id
                ],
            }
            for d in pdata.get("days", [])
        ]

    cost, warnings, route_summary = _build_cost_and_warnings(
        r.origin, city, str(r.start_date), nights, n_days, new_travelers, new_budget, new_days, by_id
    )

    pdata.update(
        travelers=new_travelers,
        budget=new_budget,
        days=new_days,
        cost=cost,
        warnings=warnings,
        route_summary=route_summary,
    )
    r.title = new_title
    r.travelers = new_travelers
    r.budget = new_budget
    r.total_cost = cost["total"]
    r.data = pdata
    db.commit()
    clean_data = {k: v for k, v in pdata.items() if k != "share_token"}
    return {"id": r.id, "title": r.title, "message": "Rencana perjalanan berhasil diperbarui", **clean_data}


# ---------- RF-11 Penghapusan Rencana Perjalanan (UC-13) ----------
@app.delete("/itineraries/{iid}")
def delete_itinerary(iid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(Itinerary, iid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Rencana tidak ditemukan")
    share_token = (r.data or {}).get("share_token")
    if share_token:
        cache.r.delete(f"share:{share_token}")
    db.execute(sa_delete(ShareLink).where(ShareLink.itinerary_id == iid))
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

    # B7: simpan di tabel ShareLink dengan masa berlaku agar pencarian O(1) via primary key & kedaluwarsa 7 hari ditegakkan
    exp_at = datetime.now(timezone.utc) + timedelta(days=settings.share_ttl_days)
    link = db.get(ShareLink, share_token)
    if link:
        link.expires_at = exp_at
    else:
        db.add(ShareLink(token=share_token, itinerary_id=r.id, expires_at=exp_at))
    db.commit()
    cache.r.set(f"share:{share_token}", r.id, ex=settings.share_ttl_days * 86400)
    return {
        "id": r.id,
        "share_token": share_token,
        "share_url": f"/?share={share_token}",
        "expires_at": exp_at.isoformat(),
        "message": "Tautan berbagi berhasil dibuat",
    }


@app.get("/shared/{token}")
def get_shared_itinerary(token: str, db: Session = Depends(get_db)):
    if not re.fullmatch(r"[a-f0-9]{16,64}", token):
        raise HTTPException(404, "Rencana perjalanan ini tidak lagi tersedia")

    # B7: cek tabel ShareLink berdasarkan primary key (tanpa full-table scan) dan validasi masa berlaku
    link = db.get(ShareLink, token)
    now_utc = datetime.now(timezone.utc)
    if link:
        exp = link.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now_utc:
            db.delete(link)
            db.commit()
            try:
                cache.r.delete(f"share:{token}")
            except Exception:
                pass
            raise HTTPException(404, "Rencana perjalanan ini tidak lagi tersedia")
        r = db.get(Itinerary, link.itinerary_id)
    else:
        try:
            iid = cache.r.get(f"share:{token}")
        except Exception:
            iid = None
        r = db.get(Itinerary, iid) if iid else None

    if not r or (r.data or {}).get("share_token") != token:
        raise HTTPException(404, "Rencana perjalanan ini tidak lagi tersedia")
    clean_data = {k: v for k, v in (r.data or {}).items() if k != "share_token"}
    if "days" in clean_data and "route_summary" not in clean_data:
        clean_data["route_summary"] = _enrich_route_metrics(clean_data["days"])
    return {"id": r.id, "title": r.title, "shared": True, **clean_data}


# ---------- Sajikan Frontend Otomatis di http://localhost:8000 ----------
_frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(_frontend_path):
    app.mount("/", StaticFiles(directory=_frontend_path, html=True), name="frontend")
