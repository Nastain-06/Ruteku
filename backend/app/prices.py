"""Integrasi harga real-time: adapter provider + cache Redis (TTL) + fallback data terakhir."""
import hashlib
import time
from datetime import datetime, timezone
from . import cache
from .config import settings

BASE_HOTEL = {"Bali": 550_000, "Yogyakarta": 350_000, "Labuan Bajo": 650_000, "Derawan": 500_000}
BASE_HOTEL_DEFAULT = 450_000
BASE_TRANSPORT_PP = 1_400_000  # tiket pulang-pergi per orang


class MockPriceProvider:
    """Pengganti API OTA. Harga berfluktuasi tiap 10 menit agar efek 'real-time' terlihat.
    Untuk API asli: buat kelas lain dengan method quote() yang sama, lalu ganti PROVIDER."""
    name = "mock-ota"

    def quote(self, kind: str, key: str, base: int) -> int:
        if settings.mock_fail:
            raise RuntimeError("Penyedia harga tidak merespons")
        bucket = int(time.time() // 600)
        h = int(hashlib.md5(f"{kind}:{key}:{bucket}".encode()).hexdigest()[:6], 16)
        return int(round(base * (0.92 + (h % 1700) / 10000), -3))


PROVIDER = MockPriceProvider()


def get_price(kind: str, key: str, day: str, base: int) -> dict:
    ck, lk = f"price:{kind}:{key}:{day}", f"price_last:{kind}:{key}:{day}"
    try:
        hit = cache.get_json(ck)
    except Exception:
        hit = None
    if hit:
        return {**hit, "from_cache": True, "stale": False}
    try:
        rec = {"value": PROVIDER.quote(kind, key, base), "source": PROVIDER.name,
               "fetched_at": datetime.now(timezone.utc).isoformat()}
        try:
            cache.set_json(ck, rec, settings.price_ttl_seconds)
            cache.set_json(lk, rec, 7 * 86400)
        except Exception:
            pass
        return {**rec, "from_cache": False, "stale": False}
    except Exception:
        try:
            last = cache.get_json(lk)  # fallback: harga terakhir, ditandai stale
        except Exception:
            last = None
        if last:
            return {**last, "from_cache": True, "stale": True}
        return {"value": None, "source": None, "fetched_at": None, "from_cache": False, "stale": False}
