import json
import redis
from .config import settings

try:
    _r = redis.from_url(settings.redis_url, decode_responses=True)
    _r.ping()  # cek koneksi
    r = _r
except Exception:
    import fakeredis
    r = fakeredis.FakeRedis(decode_responses=True)
    print("⚠ Redis tidak tersedia, menggunakan fakeredis (data cache hilang saat restart)")


def get_json(key: str):
    v = r.get(key)
    return json.loads(v) if v else None


def set_json(key: str, value, ttl: int):
    r.set(key, json.dumps(value), ex=ttl)
