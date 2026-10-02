"""CORS: only the configured dashboard origin may call the API from a browser."""

from httpx import AsyncClient

from app.core.config import settings

PREFLIGHT = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"}


async def test_dashboard_origin_is_allowed(client: AsyncClient) -> None:
    origin = settings.cors_origins[0]
    response = await client.options("/approvals/pending", headers={"Origin": origin, **PREFLIGHT})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in response.headers


async def test_other_origins_are_refused(client: AsyncClient) -> None:
    response = await client.options("/approvals/pending", headers={"Origin": "https://evil.example", **PREFLIGHT})

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


async def test_unneeded_methods_are_refused(client: AsyncClient) -> None:
    headers = {"Origin": settings.cors_origins[0], "Access-Control-Request-Method": "DELETE"}
    assert (await client.options("/approvals/pending", headers=headers)).status_code == 400
