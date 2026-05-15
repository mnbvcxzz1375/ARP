from fastapi.testclient import TestClient

from app.exceptions import DomainException
from app.main import app
from app.protocol.constants import ErrorCode


async def raise_domain_exception() -> None:
    raise DomainException(
        ErrorCode.AGENT_NOT_FOUND,
        "Agent was not found.",
        status_code=404,
        details={"agent_id": "agt_missing"},
    )


def test_domain_exception_serializes_standard_error_response() -> None:
    app.add_api_route("/__test__/domain-error", raise_domain_exception, methods=["GET"])
    client = TestClient(app)

    response = client.get("/__test__/domain-error")

    assert response.status_code == 404
    assert response.json() == {
        "type": "error",
        "error": {
            "code": "AGENT_NOT_FOUND",
            "message": "Agent was not found.",
            "details": {"agent_id": "agt_missing"},
        },
    }

