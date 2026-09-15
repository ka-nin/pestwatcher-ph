from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central app configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000

    # Comma-separated list of origins allowed to call this API.
    # Includes the Vite dev servers for admin-web and user-mobile (both default
    # to :5173; user-mobile also uses basicSsl, hence the https:// entries).
    # If you run both apps at once, Vite will bump one of them to :5174/:5175 —
    # those are included too so either ordering works without editing .env.
    cors_origins: str = (
        "http://localhost:5173,"
        "https://localhost:5173,"
        "http://localhost:5174,"
        "https://localhost:5174,"
        "http://localhost:5175,"
        "https://localhost:5175,"
        "http://localhost:19006,"
        "exp://localhost:19000"
    )

    upload_dir: str = "uploads"

    # HS256 signing secret for admin/LGU auth tokens (app/security.py). The
    # default below is fine for local dev only — .env.example generates a
    # real random one via `openssl rand -base64 48` and every deployment
    # should set its own so tokens can't be forged across environments.
    jwt_secret: str = "dev-only-insecure-secret-change-me"
    jwt_expire_minutes: int = 60 * 12

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
