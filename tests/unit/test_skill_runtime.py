from pathlib import Path

import pytest

from genesis.contracts import CanonicalContractCatalog
from genesis.runtime.context import DataClassification, ExecutionContextView
from genesis.runtime.limits import ExecutionBudget
from genesis.skills.authorization import SkillAuthorizationSnapshot
from genesis.skills.loader import (
    FileSystemSkillLoader,
    SkillFailureCode,
    SkillPackageError,
    SkillReference,
)
from genesis.skills.progressive_loading import ProgressiveSkillLoader
from genesis.skills.runtime import SkillRuntime, SkillRuntimeStatus
from genesis.skills.selection import SkillSelectionStatus, SkillSelector

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


def write_package(
    root: Path,
    name: str,
    *,
    skill_id: str,
    version: str = "1.0.0",
    purpose: str = "Analyze technology architecture.",
    tool_ids: tuple[str, ...] = (),
    permission_refs: tuple[str, ...] = (),
    scope_refs: tuple[str, ...] = (),
) -> None:
    package = root / name
    package.mkdir()
    tools = ", ".join(tool_ids)
    permissions = ", ".join(permission_refs)
    scopes = ", ".join(scope_refs)
    (package / "skill.yaml").write_text(
        f"""
skill_id: {skill_id}
skill_version: {version}
name: {name}
description: {purpose}
purpose: {purpose}
when_to_use: [{purpose}]
input_schema_ref: https://schemas.alos.dev/v1/research/research-request.schema.json
output_schema_ref: https://schemas.alos.dev/v1/research/research-result.schema.json
procedure: [Analyze evidence.]
required_tool_ids: [{tools}]
permission_refs: [{permissions}]
scope_refs: [{scopes}]
evidence_requirements: [Cite evidence.]
restrictions: [Do not execute actions.]
failure_modes: [Insufficient evidence.]
escalation: [Request information.]
evaluation: [Claims are cited.]
""".strip(),
        encoding="utf-8",
    )
    (package / "SKILL.md").write_text(
        f"# {name}\n\nUnique {skill_id} instructions.", encoding="utf-8"
    )


def loader() -> FileSystemSkillLoader:
    return FileSystemSkillLoader(contracts=CanonicalContractCatalog(CONTRACTS_ROOT))


def reference(skill_id: str, version: str = "1.0.0") -> SkillReference:
    return SkillReference(skill_id=skill_id, skill_version=version)


def authorization(
    refs: tuple[SkillReference, ...],
    tools: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
    scopes: tuple[str, ...] = (),
) -> SkillAuthorizationSnapshot:
    return SkillAuthorizationSnapshot(
        tenant_id="tenant_test",
        organization_id="organization_test",
        workspace_id="workspace_test",
        correlation_id="corr_skill_test",
        authorized_skill_refs=refs,
        permission_refs=permissions,
        scope_refs=scopes,
        allowed_tool_ids=tools,
    )


def execution_context() -> ExecutionContextView:
    return ExecutionContextView(
        tenant_id="tenant_test",
        organization_id="organization_test",
        workspace_id="workspace_test",
        actor_id="actor_test",
        authority_context={"role": "runner", "authority_level": "SYSTEM"},
        permission_refs=("permission.a", "permission.b"),
        allowed_tool_ids=("tool.a", "tool.b"),
        scope_refs=("scope.x", "scope.y"),
        data_classification=DataClassification.INTERNAL,
        correlation_id="corr_skill_test",
        execution_budget=ExecutionBudget(max_steps=1),
    )


def test_unauthorized_package_cannot_be_selected(tmp_path: Path) -> None:
    write_package(tmp_path, "technology", skill_id="skill.research.technology")
    result = SkillSelector().select(
        loader().discover(tmp_path),
        authorized_refs=(),
        goal="technology architecture",
        backend_allowed_tool_ids=(),
    )
    assert result.selected == ()
    assert result.unavailable[0].status is SkillSelectionStatus.UNAUTHORIZED


def test_version_mismatch_has_no_silent_fallback(tmp_path: Path) -> None:
    write_package(tmp_path, "technology", skill_id="skill.research.technology")
    result = SkillSelector().select(
        loader().discover(tmp_path),
        authorized_refs=(reference("skill.research.technology", "2.0.0"),),
        goal="technology architecture",
        backend_allowed_tool_ids=(),
    )
    assert result.selected == ()
    assert any(item.status is SkillSelectionStatus.VERSION_MISMATCH for item in result.unavailable)


def test_selection_is_deterministic_explainable_and_bounded(tmp_path: Path) -> None:
    write_package(tmp_path, "zeta", skill_id="skill.zeta")
    write_package(tmp_path, "alpha", skill_id="skill.alpha")
    refs = (reference("skill.zeta"), reference("skill.alpha"))
    descriptors = loader().discover(tmp_path)
    first = SkillSelector().select(
        descriptors,
        authorized_refs=refs,
        goal="technology architecture",
        backend_allowed_tool_ids=(),
        maximum_selected=1,
    )
    second = SkillSelector().select(
        tuple(reversed(descriptors)),
        authorized_refs=refs,
        goal="technology architecture",
        backend_allowed_tool_ids=(),
        maximum_selected=1,
    )
    assert first.selected == second.selected
    assert first.selected[0].reference.skill_id == "skill.alpha"
    assert first.selected[0].reason.startswith("Matched authorized metadata terms")


def test_required_tools_use_tightest_intersection_without_mutation(tmp_path: Path) -> None:
    write_package(
        tmp_path,
        "technology",
        skill_id="skill.research.technology",
        tool_ids=("source.search_context",),
    )
    backend_tools = ["source.search_context", "research.external.retrieve"]
    agent_tools = ["research.external.retrieve"]
    result = SkillSelector().select(
        loader().discover(tmp_path),
        authorized_refs=(reference("skill.research.technology"),),
        goal="technology architecture",
        backend_allowed_tool_ids=backend_tools,
        agent_allowed_tool_ids=agent_tools,
    )
    assert result.selected == ()
    assert result.effective_tool_ids == ("research.external.retrieve",)
    assert result.unavailable[0].status is SkillSelectionStatus.REQUIRED_TOOL_UNAVAILABLE
    assert backend_tools == ["source.search_context", "research.external.retrieve"]
    assert agent_tools == ["research.external.retrieve"]


def test_runtime_loads_only_selected_instructions(tmp_path: Path) -> None:
    write_package(tmp_path, "technology", skill_id="skill.research.technology")
    write_package(
        tmp_path,
        "management",
        skill_id="skill.research.management",
        purpose="Review management KPI governance.",
    )
    result = SkillRuntime(loader=loader()).prepare(
        tmp_path,
        authorization=authorization(
            (
                reference("skill.research.technology"),
                reference("skill.research.management"),
            )
        ),
        goal="technology architecture",
    )
    assert result.status is SkillRuntimeStatus.READY
    assert len(result.loaded_skills) == 1
    assert result.loaded_skills[0].specification.skill_id == "skill.research.technology"
    assert "management" not in result.loaded_skills[0].instructions


def test_progressive_loader_rejects_nonselected_and_over_bound_outcomes(tmp_path: Path) -> None:
    write_package(tmp_path, "technology", skill_id="skill.research.technology")
    descriptor = loader().discover(tmp_path)[0]
    unauthorized = (
        SkillSelector()
        .select(
            (descriptor,),
            authorized_refs=(),
            goal="technology architecture",
            backend_allowed_tool_ids=(),
        )
        .unavailable
    )
    with pytest.raises(SkillPackageError) as rejected:
        ProgressiveSkillLoader(loader()).load_selected(unauthorized)
    assert rejected.value.code is SkillFailureCode.UNAUTHORIZED

    selected = (
        SkillSelector()
        .select(
            (descriptor,),
            authorized_refs=(reference("skill.research.technology"),),
            goal="technology architecture",
            backend_allowed_tool_ids=(),
        )
        .selected
    )
    with pytest.raises(SkillPackageError) as bounded:
        ProgressiveSkillLoader(loader(), maximum_loaded=1).load_selected((*selected, *selected))
    assert bounded.value.code is SkillFailureCode.LOAD_LIMIT_EXCEEDED


def test_permission_and_scope_prerequisites_fail_closed(tmp_path: Path) -> None:
    write_package(tmp_path, "technology", skill_id="skill.research.technology")
    manifest_path = tmp_path / "technology" / "skill.yaml"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8")
        + "\npermission_refs: [research.read]\nscope_refs: [scope.research]",
        encoding="utf-8",
    )
    result = SkillSelector().select(
        loader().discover(tmp_path),
        authorized_refs=(reference("skill.research.technology"),),
        goal="technology architecture",
        backend_allowed_tool_ids=(),
        backend_permission_refs=(),
        backend_scope_refs=("scope.research",),
    )
    assert result.selected == ()
    assert result.unavailable[0].status is SkillSelectionStatus.REQUIRED_PERMISSION_UNAVAILABLE


@pytest.mark.parametrize(
    ("permissions", "scopes", "tools", "expected_status"),
    [
        (("permission.b",), (), (), SkillSelectionStatus.REQUIRED_PERMISSION_UNAVAILABLE),
        ((), ("scope.y",), (), SkillSelectionStatus.REQUIRED_SCOPE_UNAVAILABLE),
        ((), (), ("tool.b",), SkillSelectionStatus.REQUIRED_TOOL_UNAVAILABLE),
    ],
)
def test_runtime_uses_agent_narrowed_authority_for_every_dimension(
    tmp_path: Path,
    permissions: tuple[str, ...],
    scopes: tuple[str, ...],
    tools: tuple[str, ...],
    expected_status: SkillSelectionStatus,
) -> None:
    write_package(
        tmp_path,
        "technology",
        skill_id="skill.research.technology",
        permission_refs=permissions,
        scope_refs=scopes,
        tool_ids=tools,
    )
    narrowed = SkillAuthorizationSnapshot.from_backend(
        execution_context(),
        authorized_skill_refs=(reference("skill.research.technology"),),
        agent_skill_refs=(reference("skill.research.technology"),),
        agent_permission_refs=("permission.a",),
        agent_scope_refs=("scope.x",),
        agent_allowed_tool_ids=("tool.a",),
    )

    result = SkillRuntime(loader=loader()).prepare(
        tmp_path,
        authorization=narrowed,
        goal="technology architecture",
    )

    assert narrowed.permission_refs == ("permission.a",)
    assert narrowed.scope_refs == ("scope.x",)
    assert narrowed.allowed_tool_ids == ("tool.a",)
    assert result.status is SkillRuntimeStatus.BLOCKED
    assert result.selection.unavailable[0].status is expected_status


def test_runtime_accepts_skill_with_matching_narrowed_authority(tmp_path: Path) -> None:
    write_package(
        tmp_path,
        "technology",
        skill_id="skill.research.technology",
        permission_refs=("permission.a",),
        scope_refs=("scope.x",),
        tool_ids=("tool.a",),
    )
    narrowed = SkillAuthorizationSnapshot.from_backend(
        execution_context(),
        authorized_skill_refs=(reference("skill.research.technology"),),
        agent_skill_refs=(reference("skill.research.technology"),),
        agent_permission_refs=("permission.a",),
        agent_scope_refs=("scope.x",),
        agent_allowed_tool_ids=("tool.a",),
    )

    result = SkillRuntime(loader=loader()).prepare(
        tmp_path,
        authorization=narrowed,
        goal="technology architecture",
    )

    assert result.status is SkillRuntimeStatus.READY
