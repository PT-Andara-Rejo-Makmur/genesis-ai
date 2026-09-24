import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFORCE_ROOT = ROOT / "src" / "genesis" / "control_plane" / "workforce"

FORBIDDEN_IMPORTS = (
    "genesis.adapters",
    "openai",
    "anthropic",
    "pydantic_ai",
    "langgraph",
    "mcp",
    "alos",
    "sqlalchemy",
    "psycopg",
    "fastapi",
    "httpx",
    "requests",
)

FORBIDDEN_AUTHORITY_METHODS = {
    "approve",
    "release",
    "activate",
    "register",
    "grant_permission",
    "grant_scope",
    "persist",
    "execute",
}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_workforce_factory_has_no_adapter_provider_database_or_web_dependency() -> None:
    violations: list[str] = []
    for path in WORKFORCE_ROOT.rglob("*.py"):
        for module in imported_modules(path):
            if module.startswith(FORBIDDEN_IMPORTS):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert violations == []


def test_workforce_factory_exposes_no_authoritative_lifecycle_or_execution_method() -> None:
    violations: list[str] = []
    for path in WORKFORCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in FORBIDDEN_AUTHORITY_METHODS
            ):
                violations.append(f"{path.relative_to(ROOT)}:{node.name}")
    assert violations == []


def test_workforce_composition_uses_existing_capability_factory() -> None:
    composition = (WORKFORCE_ROOT / "composition.py").read_text(encoding="utf-8")
    assert "CapabilityFactory" in composition
    assert ".analyze(" in composition
    assert "AgentDraftProposal(" not in composition


def test_workforce_source_does_not_encode_census_targets_or_agent_classes() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(WORKFORCE_ROOT.rglob("*.py"))
    )
    for census in ("62", "147", "420", "501", "710"):
        assert census not in source
    assert "class BusinessAgent" not in source


def test_workforce_production_has_no_vendor_fixture_knowledge() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(WORKFORCE_ROOT.rglob("*.py"))
    ).casefold()
    fixture_terms = (
        "vendor.performance",
        "schedule.monitoring",
        "quality.monitoring",
        "material.compliance",
        "defect.detection",
        "vendor.risk.analysis",
    )
    assert all(term not in source for term in fixture_terms)
