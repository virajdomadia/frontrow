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


async def test_every_response_is_nosniff(client: AsyncClient) -> None:
    for path in ("/health", "/nope", "/openapi.json", "/docs"):
        res = await client.get(path)
        assert res.headers["x-content-type-options"] == "nosniff", path


async def test_docs_pin_swagger_ui(client: AsyncClient) -> None:
    res = await client.get("/docs")
    assert res.status_code == 200
    assert "swagger-ui-dist@5." in res.text and "swagger-ui-dist@5/" not in res.text
