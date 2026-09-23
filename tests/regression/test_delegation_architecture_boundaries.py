from pathlib import Path

DELEGATION_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "genesis" / "orchestration" / "delegation"
)


def delegation_source() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in DELEGATION_ROOT.glob("*.py"))


def test_delegation_core_has_no_backend_database_http_or_provider_adapter() -> None:
    source = delegation_source().lower()
    forbidden = (
        "import alos",
        "from alos",
        "sqlalchemy",
        "psycopg",
        "import requests",
        "import httpx",
        "openai",
        "anthropic",
        "toolexecutor",
        "celery",
        "rq.queue",
    )
    assert all(item not in source for item in forbidden)


def test_delegation_core_does_not_recursively_invoke_runtime_or_persist_children() -> None:
    source = delegation_source()
    assert "AgentRuntimeEngine" not in source
    assert ".run(" not in source
    assert "session.add" not in source
    assert "commit(" not in source
