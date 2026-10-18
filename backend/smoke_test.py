"""Uji alur utama tanpa Postgres/Redis asli: sqlite + fakeredis.  Jalankan: python smoke_test.py"""
import os
os.environ["DATABASE_URL"] = "sqlite:///./smoke.db"
import fakeredis
from app import cache
cache.r = fakeredis.FakeRedis(decode_responses=True)
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

with TestClient(app) as c:
    reg = {"email": "a@b.com", "password": "rahasia123", "full_name": "Tes"}
    assert c.post("/auth/register", json=reg).status_code == 201
    assert c.post("/auth/register", json=reg).status_code == 400
    assert c.post("/auth/login", json={"email": "a@b.com", "password": "salah"}).status_code == 401
    tok = c.post("/auth/login", json={"email": "a@b.com", "password": "rahasia123"}).json()["access_token"]
    H = {"Authorization": f"Bearer {tok}"}
    assert len(c.get("/destinations", params={"location": "Bali"}).json()) == 5
    body = {"origin": "Samarinda", "destination": "Bali", "start_date": "2026-12-01", "end_date": "2026-12-04",
            "travelers": 2, "budget": 9000000, "interests": ["alam"]}
    p1 = c.post("/itineraries/generate", json=body, headers=H).json()
    assert p1["cost"]["total"] > 0 and len(p1["days"]) == 4, p1
    p2 = c.post("/itineraries/generate", json=body, headers=H).json()
    assert p2["cost"]["hotel"]["unit"]["from_cache"] is True  # cache Redis bekerja
    print("total:", p1["cost"]["total"], "| ai_used:", p1["ai_used"], "| cache hit: True")
    settings.mock_fail = True  # simulasi API harga down pada tanggal tanpa data tersimpan
    p4 = c.post("/itineraries/generate", json={**body, "start_date": "2026-12-10", "end_date": "2026-12-12"}, headers=H).json()
    assert any("tidak tersedia" in w for w in p4["warnings"]), p4["warnings"]
    settings.mock_fail = False
    sid = c.post("/itineraries", json={"plan_id": p1["plan_id"], "title": "Liburan Bali"}, headers=H).json()["id"]
    assert len(c.get("/itineraries", headers=H).json()) == 1
    assert c.get(f"/itineraries/{sid}", headers=H).json()["cost"]["total"] == p1["cost"]["total"]
    assert c.post("/auth/logout", headers=H).status_code == 200
    assert c.get("/itineraries", headers=H).status_code == 401  # token di-blacklist
print("SEMUA UJI LULUS")
try:
    os.remove("smoke.db")
except OSError:
    pass

