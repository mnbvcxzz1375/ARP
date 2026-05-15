from pathlib import Path


def test_protocol_schema_files_exist() -> None:
    # Try repo-relative path (works in local dev)
    try:
        schema_dir = Path(__file__).parents[3] / "packages" / "protocol" / "schemas"
    except IndexError:
        # In Docker the path is shorter; schemas are not in the Docker image.
        # Skip gracefully rather than failing.
        import pytest
        pytest.skip("Schema files not available in this environment")
        return

    expected = {
        "envelope.schema.json",
        "agent.schema.json",
        "task.schema.json",
        "message.schema.json",
        "connection.schema.json",
        "approval.schema.json",
        "error.schema.json",
    }

    assert expected == {path.name for path in schema_dir.glob("*.schema.json")}