from fastapi.testclient import TestClient

from app.main import app


def test_healthz() -> None:
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


class TestCORS:
    """Verify CORSMiddleware is installed and returns correct preflight headers."""

    ORIGIN = "http://localhost:5173"

    def test_preflight_allows_dev_origin(self) -> None:
        client = TestClient(app)
        resp = client.options(
            "/v1/dashboard/auth/login",
            headers={
                "Origin": self.ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["access-control-allow-origin"] == self.ORIGIN
        assert resp.headers["access-control-allow-credentials"] == "true"
        assert "POST" in resp.headers["access-control-allow-methods"]

    def test_preflight_allows_csrf_header(self) -> None:
        client = TestClient(app)
        resp = client.options(
            "/v1/dashboard/auth/login",
            headers={
                "Origin": self.ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-CSRF-Token",
            },
        )
        assert resp.status_code == 200
        assert "X-CSRF-Token" in resp.headers["access-control-allow-headers"]

    def test_preflight_rejects_unknown_origin(self) -> None:
        client = TestClient(app)
        resp = client.options(
            "/v1/dashboard/auth/login",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        # When origin is not allowed, CORSMiddleware still returns 200 but
        # omits access-control-allow-origin (or sets it to the empty string).
        assert "access-control-allow-origin" not in resp.headers or \
               resp.headers.get("access-control-allow-origin") == ""

    def test_actual_request_cors_headers(self) -> None:
        """Non-preflight request from allowed origin includes CORS headers."""
        client = TestClient(app)
        resp = client.post(
            "/v1/dashboard/auth/login",
            json={"username": "noone", "api_key": "nope"},
            headers={"Origin": self.ORIGIN},
        )
        # Even a 401 should include CORS headers so the browser can read the response
        assert resp.headers.get("access-control-allow-origin") == self.ORIGIN

