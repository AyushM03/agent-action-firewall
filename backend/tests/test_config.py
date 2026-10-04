from app.core.config import Settings, to_asyncpg_url


def test_neon_style_url_is_converted_for_asyncpg():
    url = "postgresql://user:pw@ep-x.eu-central-1.aws.neon.tech/db?sslmode=require&channel_binding=require"
    assert to_asyncpg_url(url) == "postgresql+asyncpg://user:pw@ep-x.eu-central-1.aws.neon.tech/db?ssl=require"


def test_postgres_scheme_is_converted():
    assert to_asyncpg_url("postgres://u:p@h:5432/db") == "postgresql+asyncpg://u:p@h:5432/db"


def test_asyncpg_url_is_left_alone():
    url = "postgresql+asyncpg://aaf_backend:pw@localhost:5434/agent_firewall"
    assert to_asyncpg_url(url) == url


def test_other_driver_is_left_alone():
    url = "postgresql+psycopg://u:p@h/db?sslmode=require"
    assert to_asyncpg_url(url) == url


def test_empty_url_stays_empty():
    assert to_asyncpg_url("") == ""


def test_settings_normalize_both_database_urls():
    settings = Settings(
        _env_file=None,
        database_url="postgresql://app:pw@h/db?sslmode=require",
        migration_database_url="postgres://owner:pw@h/db?sslmode=require",
    )
    assert settings.database_url == "postgresql+asyncpg://app:pw@h/db?ssl=require"
    assert settings.owner_database_url == "postgresql+asyncpg://owner:pw@h/db?ssl=require"
