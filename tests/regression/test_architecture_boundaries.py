import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "genesis"
FORBIDDEN_DOMAIN_IMPORTS = ("genesis.adapters", "pydantic_ai", "langgraph", "mcp")
DIRECT_PROVIDER_IMPORTS = ("openai", "anthropic", "google.generativeai", "google.genai")


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_domain_does_not_import_framework_adapters() -> None:
    violations: list[str] = []
    for path in SOURCE.rglob("*.py"):
        if "adapters" in path.relative_to(SOURCE).parts:
            continue
        for module in imported_modules(path):
            if module.startswith(FORBIDDEN_DOMAIN_IMPORTS):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert violations == []


def test_agent_domain_has_no_direct_provider_dependency() -> None:
    violations: list[str] = []
    for path in (SOURCE / "agents").rglob("*.py"):
        for module in imported_modules(path):
            if module.startswith(DIRECT_PROVIDER_IMPORTS):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert violations == []


def test_only_one_master_coordinator_exists() -> None:
    coordinator_classes: list[str] = []
    for path in SOURCE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        coordinator_classes.extend(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name.endswith("Coordinator")
        )
    assert coordinator_classes == ["MasterCoordinator"]
