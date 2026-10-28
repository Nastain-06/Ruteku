import secrets
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg2://ruteku:ruteku@localhost:5432/ruteku"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = ""
    jwt_hours: int = 24
    openai_api_key: str = ""
    openai_model: str = ""
    price_ttl_seconds: int = 1800  # NFR-17: TTL maks 30 menit
    mock_fail: bool = False        # simulasi penyedia harga down (untuk demo fallback)
    cors_origins: str = "http://localhost:8000"
    # B3: header X-Forwarded-For hanya dipercaya jika request datang dari proxy yang terdaftar di sini
    trusted_proxies: str = "127.0.0.1,::1,testclient"
    # B5: prototipe belum punya layanan email, jadi kode OTP ditampilkan di respons. WAJIB False di produksi.
    demo_mode: bool = True
    share_ttl_days: int = 7
    # diisi otomatis: True jika JWT_SECRET tidak di-set sehingga secret dibuat acak (sesi hilang saat restart)
    jwt_secret_ephemeral: bool = False

    @model_validator(mode="after")
    def _ensure_jwt_secret(self):
        if not self.jwt_secret:
            self.jwt_secret = secrets.token_hex(32)
            self.jwt_secret_ephemeral = True
        elif len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET minimal 32 karakter")
        return self

    @property
    def trusted_proxy_set(self) -> set[str]:
        return {x.strip() for x in self.trusted_proxies.split(",") if x.strip()}


settings = Settings()
