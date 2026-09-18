from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True, "service": "frontrow-api", "version": "0.1.0"}
    assert res.headers["x-request-id"]


async def test_unknown_route_is_the_envelope(client: AsyncClient) -> None:
    res = await client.get("/nope")
    assert res.status_code == 404
    assert res.json() == {"error": {"code": "not_found", "message": "Not Found"}}
