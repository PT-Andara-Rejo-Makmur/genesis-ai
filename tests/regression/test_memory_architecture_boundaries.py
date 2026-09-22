from pathlib import Path

MEMORY_ROOT = Path(__file__).resolve().parents[2] / "src" / "genesis" / "memory"


def test_memory_core_has_no_forbidden_runtime_or_persistence_dependencies() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in MEMORY_ROOT.rglob("*.py")
        if path.name != "backend.py"
    ).casefold()
    forbidden = (
        "from alos",
        "import alos",
        "sqlalchemy",
        "psycopg",
        "pgvector",
        "pinecone",
        "chromadb",
        "weaviate",
        "langgraph",
        "pydantic_ai",
        "import mcp",
        "import httpx",
        "requests.",
        "eval(",
        "exec(",
        "__import__(",
    )
    assert all(token not in source for token in forbidden)


def test_memory_write_policy_has_no_persistence_calls() -> None:
    source = (MEMORY_ROOT / "write" / "policy.py").read_text(encoding="utf-8").casefold()
    forbidden = ("save(", "insert(", "update(", "delete(", "commit(", "persist(")
    assert all(token not in source for token in forbidden)
