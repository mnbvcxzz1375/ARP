"""Tests for the M1 E2EE trust root: agent public_keys registration.

Covers:
  - registering an agent with composite public_keys {kem, sig, v}
  - reading them back via GET
  - using the read-back Ed25519 key to actually verify a signature
  - rejecting malformed key bundles
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.agent_service import validate_public_keys
from app.exceptions import DomainException


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def api_key(client):
    resp = await client.post(
        "/v1/auth/register",
        json={"username": f"e2ee-user-{uuid.uuid4().hex[:8]}", "key_name": "k"},
    )
    assert resp.status_code == 200
    return resp.json()["api_key"]


def _b64(raw: bytes) -> str:
    import base64

    return base64.standard_b64encode(raw).decode("ascii")


def _real_key_bundle() -> dict:
    """Generate a genuine X25519+Ed25519 bundle (real key material, freshly
    generated per test run — never a shared literal credential)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519, x25519

    kem_pub = (
        x25519.X25519PrivateKey.generate()
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    )
    sig_private = ed25519.Ed25519PrivateKey.generate()
    sig_pub = sig_private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {"kem": _b64(kem_pub), "sig": _b64(sig_pub), "v": 1}, sig_private


class TestValidatePublicKeys:
    def test_valid_bundle_normalizes(self):
        bundle, _ = _real_key_bundle()
        validated = validate_public_keys(bundle)
        assert validated == bundle
        assert set(validated) == {"kem", "sig", "v"}

    def test_version_defaults_to_1(self):
        bundle, _ = _real_key_bundle()
        del bundle["v"]
        assert validate_public_keys(bundle)["v"] == 1

    def test_rejects_bad_base64(self):
        with pytest.raises(DomainException):
            validate_public_keys({"kem": "!!!not-base64!!!", "sig": "A" * 44, "v": 1})

    def test_rejects_wrong_raw_length(self):
        with pytest.raises(DomainException):
            validate_public_keys(
                {"kem": _b64(b"\x00" * 31), "sig": _b64(b"\x00" * 32), "v": 1}
            )

    def test_rejects_unknown_version(self):
        bundle, _ = _real_key_bundle()
        bundle["v"] = 2
        with pytest.raises(DomainException):
            validate_public_keys(bundle)

    def test_rejects_missing_field(self):
        bundle, _ = _real_key_bundle()
        del bundle["sig"]
        with pytest.raises(DomainException):
            validate_public_keys(bundle)

    def test_rejects_non_object(self):
        with pytest.raises(DomainException):
            validate_public_keys(["kem", "sig"])  # type: ignore[arg-type]


class TestAgentPublicKeysApi:
    async def test_register_and_read_back_keys(self, client, api_key):
        bundle, sig_private = _real_key_bundle()
        resp = await client.post(
            "/v1/agents",
            json={
                "name": "E2EE Agent",
                "runtime": "test",
                "public_keys": bundle,
            },
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 201, resp.text
        created = resp.json()
        assert created["public_keys"] == bundle

        agent_id = created["agent_id"]
        resp = await client.get(
            f"/v1/agents/{agent_id}", headers={"X-API-Key": api_key}
        )
        assert resp.status_code == 200
        read_back = resp.json()["public_keys"]
        assert read_back["kem"] == bundle["kem"]
        assert read_back["sig"] == bundle["sig"]
        assert read_back["v"] == 1

    async def test_read_back_sig_key_verifies_signature(
        self, client, api_key
    ):
        """Acceptance: use the key read back from the API to verify a real
        Ed25519 signature over a message (not just field equality)."""
        bundle, sig_private = _real_key_bundle()
        resp = await client.post(
            "/v1/agents",
            json={
                "name": "E2EE Verify Agent",
                "runtime": "test",
                "public_keys": bundle,
            },
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 201, resp.text
        agent_id = resp.json()["agent_id"]

        resp = await client.get(
            f"/v1/agents/{agent_id}", headers={"X-API-Key": api_key}
        )
        read_back = resp.json()["public_keys"]

        import base64

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        sig_pub_bytes = base64.standard_b64decode(read_back["sig"])
        assert sig_pub_bytes == base64.standard_b64decode(bundle["sig"])
        sig_pub = ed25519.Ed25519PublicKey.from_public_bytes(sig_pub_bytes)

        message = f"agent:{agent_id}:e2ee-binding".encode("utf-8")
        signature = sig_private.sign(message)
        sig_pub.verify(signature, message)  # raises on failure

        # And a wrong message must fail verification
        with pytest.raises(Exception):
            sig_pub.verify(signature, b"agent:other:e2ee-binding")

    async def test_register_without_keys(self, client, api_key):
        resp = await client.post(
            "/v1/agents",
            json={"name": "Plaintext Agent", "runtime": "test"},
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["public_keys"] is None

    async def test_keys_visible_in_list(self, client, api_key):
        bundle, _ = _real_key_bundle()
        resp = await client.post(
            "/v1/agents",
            json={"name": "Listed E2EE Agent", "runtime": "test", "public_keys": bundle},
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 201, resp.text
        resp = await client.get(
            "/v1/agents", headers={"X-API-Key": api_key}
        )
        assert resp.status_code == 200
        matching = [
            a for a in resp.json()["agents"] if a["public_keys"] is not None
        ]
        assert any(a["public_keys"]["kem"] == bundle["kem"] for a in matching)

    async def test_rejects_malformed_keys(self, client, api_key):
        resp = await client.post(
            "/v1/agents",
            json={
                "name": "Bad Keys Agent",
                "runtime": "test",
                "public_keys": {"kem": "!!!not-base64!!!", "sig": "A" * 44},
            },
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 422

    async def test_rejects_wrong_raw_length(self, client, api_key):
        resp = await client.post(
            "/v1/agents",
            json={
                "name": "Short Key Agent",
                "runtime": "test",
                "public_keys": {
                    "kem": _b64(b"\x00" * 31),
                    "sig": _b64(b"\x00" * 32),
                },
            },
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 422
