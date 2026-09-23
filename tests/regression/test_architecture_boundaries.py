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


def test_context_and_research_decision_have_no_direct_io_or_backend_implementation() -> None:
    roots = (
        SOURCE / "runtime" / "context",
        SOURCE / "research" / "decision.py",
    )
    forbidden = (*FORBIDDEN_BACKEND_IMPLEMENTATION_IMPORTS, "httpx", "requests", "urllib")
    violations: list[str] = []
    for root in roots:
        paths = (root,) if root.is_file() else tuple(root.rglob("*.py"))
        for path in paths:
            for module in imported_modules(path):
                if module.startswith(forbidden):
                    violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert violations == []


def test_skill_system_has_no_direct_io_framework_or_execution_bypass() -> None:
    forbidden = (
        *FORBIDDEN_BACKEND_IMPLEMENTATION_IMPORTS,
        *DIRECT_PROVIDER_IMPORTS,
        *FORBIDDEN_DOMAIN_IMPORTS,
        "httpx",
        "requests",
        "urllib",
        "genesis.runtime.execution.tool_client",
    )
    violations: list[str] = []
    for path in (SOURCE / "skills").rglob("*.py"):
        for module in imported_modules(path):
            if module.startswith(forbidden):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert violations == []


def test_skill_system_has_no_dynamic_package_execution_or_local_tool_executor() -> None:
    violations: list[str] = []
    for path in (SOURCE / "skills").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ToolExecutor":
                violations.append(f"{path.relative_to(ROOT)} defines ToolExecutor")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec", "__import__"}:
                    violations.append(f"{path.relative_to(ROOT)} calls {node.func.id}")
    assert violations == []


def test_builtin_skill_packages_are_data_only() -> None:
    packages = ROOT / "blueprints" / "skills"
    executable_files = [
        path.relative_to(ROOT)
        for path in packages.rglob("*")
        if path.is_file() and path.suffix not in {".md", ".yaml"}
    ]
    assert executable_files == []


def test_agentic_and_research_policy_have_no_io_provider_or_backend_bypass() -> None:
    roots = (
        SOURCE / "runtime" / "agentic",
        SOURCE / "research" / "decision.py",
        SOURCE / "research" / "tool_selection.py",
    )
    forbidden = (
        *FORBIDDEN_BACKEND_IMPLEMENTATION_IMPORTS,
        *DIRECT_PROVIDER_IMPORTS,
        *FORBIDDEN_DOMAIN_IMPORTS,
        "httpx",
        "requests",
        "urllib",
    )
    violations: list[str] = []
    for root in roots:
        paths = (root,) if root.is_file() else tuple(root.rglob("*.py"))
        for path in paths:
            for module in imported_modules(path):
                if module.startswith(forbidden):
                    violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert violations == []


def test_agentic_runtime_defines_no_executor_persistence_or_governance_mutation() -> None:
    forbidden_classes = {"ToolExecutor", "RunRepository", "ResearchProviderClient"}
    forbidden_functions = {
        "approve",
        "release",
        "activate",
        "persist_run",
        "save_step",
        "cancel_run",
    }
    violations: list[str] = []
    for path in (SOURCE / "runtime" / "agentic").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in forbidden_classes:
                violations.append(f"{path.relative_to(ROOT)} defines {node.name}")
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in forbidden_functions
            ):
                violations.append(f"{path.relative_to(ROOT)} defines {node.name}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec", "__import__"}:
                    violations.append(f"{path.relative_to(ROOT)} calls {node.func.id}")
    assert violations == []


def test_delegation_delegation_has_no_io_recursion_persistence_scheduler_or_research_engine() -> (
    None
):
    forbidden_imports = (
        *FORBIDDEN_BACKEND_IMPLEMENTATION_IMPORTS,
        *DIRECT_PROVIDER_IMPORTS,
        "httpx",
        "requests",
        "urllib",
        "genesis.runtime.agentic.engine",
    )
    forbidden_classes = {
        "ToolExecutor",
        "ChildRunRepository",
        "DelegationScheduler",
        "DelegationQueue",
        "ResearchOrchestrator",
    }
    forbidden_functions = {
        "persist_child",
        "schedule_child",
        "enqueue_child",
        "approve",
        "release",
    }
    violations: list[str] = []
    for path in (SOURCE / "orchestration" / "delegation").rglob("*.py"):
        for module in imported_modules(path):
            if module.startswith(forbidden_imports):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in forbidden_classes:
                violations.append(f"{path.relative_to(ROOT)} defines {node.name}")
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in forbidden_functions
            ):
                violations.append(f"{path.relative_to(ROOT)} defines {node.name}")
    assert violations == []


def test_research_research_orchestration_has_no_io_provider_or_authority_bypass() -> None:
    forbidden_imports = (
        *FORBIDDEN_BACKEND_IMPLEMENTATION_IMPORTS,
        *DIRECT_PROVIDER_IMPORTS,
        *FORBIDDEN_DOMAIN_IMPORTS,
        "httpx",
        "requests",
        "urllib",
        "chromadb",
        "faiss",
        "pinecone",
        "sentence_transformers",
    )
    forbidden_classes = {
        "ToolExecutor",
        "SourceRegistry",
        "ResearchRepository",
        "ApprovalService",
        "BacklogService",
    }
    forbidden_functions = {
        "approve",
        "release",
        "persist",
        "save",
        "create_backlog_item",
    }
    violations: list[str] = []
    for path in (SOURCE / "research" / "orchestration").rglob("*.py"):
        for module in imported_modules(path):
            if module.startswith(forbidden_imports):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in forbidden_classes:
                violations.append(f"{path.relative_to(ROOT)} defines {node.name}")
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in forbidden_functions
            ):
                violations.append(f"{path.relative_to(ROOT)} defines {node.name}")
    assert violations == []


def test_research_uses_one_generic_orchestrator_for_all_research_domains() -> None:
    definitions: list[str] = []
    for path in (SOURCE / "research").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        definitions.extend(
            f"{path.relative_to(ROOT).as_posix()}:{node.name}"
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name.endswith("ResearchOrchestrator")
        )
    assert definitions == ["src/genesis/research/orchestration/service.py:ResearchOrchestrator"]
