from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg2://ruteku:ruteku@localhost:5432/ruteku"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret"
    jwt_hours: int = 24
    openai_api_key: str = ""
    openai_model: str = ""
    price_ttl_seconds: int = 1800  # NFR-17: TTL maks 30 menit
    mock_fail: bool = False        # simulasi penyedia harga down (untuk demo fallback)
    cors_origins: str = "http://localhost:3000"


settings = Settings()
