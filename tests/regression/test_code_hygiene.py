"""Permanent production naming and structural hygiene guards."""

import ast
import re
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "genesis"

FORBIDDEN_SOURCE_PATTERNS = {
    "obsolete assurance constant": r"MVP2_H8_REGRESSION_SET",
    "obsolete research budget constant": r"H7_DEFAULT_MODEL_TOKEN_BUDGET",
    "milestone research policy": r"policy\.h7\.",
    "milestone assurance case ID": r'["\']h8\.',
    "milestone assurance set ID": r"mvp2-h8",
    "historical migration attribution": r"adapted from MVP-1",
}


def production_files() -> tuple[Path, ...]:
    return tuple(sorted(SOURCE_ROOT.rglob("*.py")))


def test_production_source_has_no_milestone_identifiers() -> None:
    violations: list[str] = []
    for path in production_files():
        source = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_SOURCE_PATTERNS.items():
            if re.search(pattern, source):
                violations.append(f"{path.relative_to(SOURCE_ROOT)}: {label}")
    assert violations == []


def test_production_docstrings_use_permanent_component_names() -> None:
    violations: list[str] = []
    milestone = re.compile(r"\bH[5-8]\b")
    for path in production_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        nodes: tuple[ast.AST, ...] = (tree, *ast.walk(tree))
        for node in nodes:
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = ast.get_docstring(node, clean=False)
                if docstring and milestone.search(docstring):
                    violations.append(f"{path.relative_to(SOURCE_ROOT)}:{node.lineno}")
    assert violations == []


def test_agent_draft_has_one_explicit_proposal_definition() -> None:
    definitions: list[tuple[str, str]] = []
    for path in production_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        definitions.extend(
            (node.name, str(path.relative_to(SOURCE_ROOT)))
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and "AgentDraft" in node.name
        )
    assert definitions == [
        ("AgentDraftProposal", "control_plane\\factory\\models.py")
    ] or definitions == [("AgentDraftProposal", "control_plane/factory/models.py")]


def test_core_runtime_has_no_one_shot_planner_types() -> None:
    runtime_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((SOURCE_ROOT / "runtime" / "agentic").glob("*.py"))
    )
    for name in ("ExecutionPlan", "RuntimePlanner", "SinglePassPlanner", "legacy_plan"):
        assert name not in runtime_source
