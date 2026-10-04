from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_JWT_SECRET = "change-me-in-.env"

# libpq-only query parameters that asyncpg doesn't accept as keyword arguments.
_LIBPQ_ONLY_PARAMS = {"channel_binding"}


def to_asyncpg_url(url: str) -> str:
    """Accept a plain libpq URL as managed hosts hand it out (e.g. Neon's
    `postgresql://...?sslmode=require&channel_binding=require`) and return the
    `postgresql+asyncpg://...?ssl=require` form SQLAlchemy's asyncpg driver needs."""
    if not url:
        return url
    parts = urlsplit(url)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    if scheme != "postgresql+asyncpg":
        return url
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key == "sslmode":
            key = "ssl"
        if key not in _LIBPQ_ONLY_PARAMS:
            query.append((key, value))
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    # The backend's own login: a member of the least-privilege `aaf_app` role (see the
    # least_privilege_app_role migration), never the table owner or a superuser.
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5434/agent_firewall"
    # Owner login, used only by Alembic (and the DB-layer tests). Empty = use database_url.
    migration_database_url: str = ""
    # Log every SQL statement (debugging only). Parameters are never logged either way.
    db_echo: bool = False
    redis_url: str = "redis://localhost:6380/0"

    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""
    gmail_sender_address: str = ""

    stripe_secret_key: str = ""

    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return to_asyncpg_url(value)

    @property
    def owner_database_url(self) -> str:
        return self.migration_database_url or self.database_url


settings = Settings()
