import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "genesis"
FORBIDDEN_DOMAIN_IMPORTS = ("genesis.adapters", "pydantic_ai", "langgraph", "mcp")
DIRECT_PROVIDER_IMPORTS = ("openai", "anthropic", "google.generativeai", "google.genai")
FORBIDDEN_BACKEND_IMPLEMENTATION_IMPORTS = (
    "alos",
    "psycopg",
    "sqlalchemy",
)


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


def test_genesis_tool_boundary_has_no_backend_adapter_or_database_import() -> None:
    violations: list[str] = []
    for path in (SOURCE / "runtime" / "execution").rglob("*.py"):
        for module in imported_modules(path):
            if module.startswith(FORBIDDEN_BACKEND_IMPLEMENTATION_IMPORTS):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert violations == []


def test_genesis_intelligence_has_no_backend_implementation_or_database_import() -> None:
    violations: list[str] = []
    for path in SOURCE.rglob("*.py"):
        for module in imported_modules(path):
            if module.startswith(FORBIDDEN_BACKEND_IMPLEMENTATION_IMPORTS):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert violations == []


def test_genesis_has_no_authoritative_tool_executor() -> None:
    definitions: list[str] = []
    for path in SOURCE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        definitions.extend(
            f"{path.relative_to(ROOT)}:{node.name}"
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "ToolExecutor"
        )
    assert definitions == []


def test_factory_exposes_no_approval_release_or_registry_mutation_service() -> None:
    forbidden_names = {
        "approve",
        "release",
        "activate",
        "register",
        "grant_permission",
        "change_scope",
    }
    violations: list[str] = []
    for path in (SOURCE / "control_plane" / "factory").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in forbidden_names
            ):
                violations.append(f"{path.relative_to(ROOT)}:{node.name}")
    assert violations == []


def test_rd_domains_do_not_define_duplicate_research_engines() -> None:
    engine_classes: list[str] = []
    for path in (SOURCE / "research" / "domains").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        engine_classes.extend(
            f"{path.relative_to(ROOT)}:{node.name}"
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name.endswith("Engine")
        )
    assert engine_classes == []
