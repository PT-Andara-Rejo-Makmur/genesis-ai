"""Permanent production naming and structural hygiene guards."""

import ast
import re
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "genesis"

MILESTONE_VOCABULARY_PATTERN = (
    r"(?i)(?<![A-Za-z0-9])"
    r"(?:H[1-8]|MVP(?:1|2)?|M2-H(?:0[1-9]|[1-9][0-9])|RC1)"
    r"(?![A-Za-z0-9])"
)

FORBIDDEN_SOURCE_PATTERNS = {
    "delivery milestone vocabulary": MILESTONE_VOCABULARY_PATTERN,
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


@pytest.mark.parametrize(
    "source",
    (
        'POLICY = "H1"',
        'CASE_ID = "h8.context.cross-tenant"',
        'RELEASE = "MVP"',
        'RELEASE = "MVP1"',
        'RELEASE = "mvp2-release"',
        'MILESTONE = "M2-H08"',
        'CANDIDATE = "RC1"',
    ),
)
def test_milestone_pattern_rejects_standalone_delivery_vocabulary(source: str) -> None:
    assert re.search(MILESTONE_VOCABULARY_PATTERN, source)


@pytest.mark.parametrize(
    "source",
    (
        'DIGEST = "sha256:a1b2c3d4"',
        "class CH1Parser: ...",
        'IDENTIFIER = "RC10"',
        'VERSION = "MVP3"',
        'VERSION = "1.0.0"',
        "# calculate pH1 before admission",
    ),
)
def test_milestone_pattern_allows_unrelated_identifiers_and_versions(source: str) -> None:
    assert re.search(MILESTONE_VOCABULARY_PATTERN, source) is None


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
                    violations.append(
                        f"{path.relative_to(SOURCE_ROOT)}:{getattr(node, 'lineno', 1)}"
                    )
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
