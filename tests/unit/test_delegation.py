from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from genesis.contracts import CanonicalContractCatalog
from genesis.orchestration.delegation import (
    AuthorityEnvelope,
    AuthorizedChildTarget,
    ChildAuthorityRequest,
    ChildObservation,
    ChildResultInvalid,
    ChildResultValidator,
    ChildTaskSpec,
    DelegationAuthorizationSnapshot,
    DelegationDenied,
    DelegationDisposition,
    DelegationGuard,
    DelegationPlanner,
    DelegationPlanningError,
    DelegationSynthesizer,
    DomainDelegationRequest,
    ResearchDelegationConstraints,
    ResearchDomainDelegationPolicy,
)
from genesis.orchestration.delegation.planner import expected_delegation_key
from genesis.research.models import ResearchDomain
from genesis.research.tool_selection import ResearchToolCategory
from genesis.runtime.context import DataClassification
from genesis.runtime.limits import ExecutionBudget

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


def authority(**changes: Any) -> AuthorityEnvelope:
    values: dict[str, Any] = {
        "tenant_id": "tenant_h6_001",
        "organization_id": "organization_h6_001",
        "workspace_id": "workspace_h6_001",
        "permission_refs": frozenset({"research.read", "documents.read"}),
        "scope_refs": frozenset({"scope.research", "scope.technology"}),
        "allowed_tool_ids": frozenset({"documents.search", "datasets.search"}),
        "data_classification": DataClassification.CONFIDENTIAL,
    }
    values.update(changes)
    return AuthorityEnvelope.model_validate(values)


def budget(**changes: Any) -> ExecutionBudget:
    values: dict[str, Any] = {
        "max_tokens": 100,
        "max_cost": 5,
        "max_steps": 4,
        "max_tool_calls": 2,
        "max_children": 2,
        "max_depth": 3,
        "timeout_seconds": 60,
        "concurrency_limit": 2,
    }
    values.update(changes)
    return ExecutionBudget.model_validate(values)


def research_constraints(**changes: Any) -> ResearchDelegationConstraints:
    values: dict[str, Any] = {
        "allowed_domains": frozenset(ResearchDomain),
        "allowed_source_categories": frozenset(
            {ResearchToolCategory.INTERNAL_DOCUMENT, ResearchToolCategory.PUBLIC_DATASET}
        ),
        "external_research_allowed": False,
        "maximum_external_cost": 0,
        "data_classification_ceiling": DataClassification.CONFIDENTIAL,
    }
    values.update(changes)
    return ResearchDelegationConstraints.model_validate(values)


def targets() -> tuple[AuthorizedChildTarget, ...]:
    return tuple(
        AuthorizedChildTarget(
            agent_id=f"agent_{domain.value.lower()}",
            agent_version="1.0.0",
            capability_ids=("capability.research",),
            research_domains=(domain,),
        )
        for domain in ResearchDomain
    )


def snapshot(**changes: Any) -> DelegationAuthorizationSnapshot:
    values: dict[str, Any] = {
        "enabled": True,
        "parent_run_id": "run_parent_h6_001",
        "root_run_id": "run_root_h6_001",
        "parent_agent_id": "agent_parent_h6",
        "parent_agent_version": "2.0.0",
        "parent_depth": 1,
        "ancestry_agent_refs": ("agent_root@1.0.0",),
        "allowed_child_targets": targets(),
        "max_depth": 3,
        "max_children": 2,
        "concurrency_preflight_limit": 2,
        "effective_parent_authority": authority(),
        "parent_budget": budget(),
        "research_constraints": research_constraints(),
    }
    values.update(changes)
    return DelegationAuthorizationSnapshot.model_validate(values)


def child_authority(**changes: Any) -> ChildAuthorityRequest:
    values: dict[str, Any] = {
        "authority": authority(
            permission_refs=frozenset({"research.read"}),
            scope_refs=frozenset({"scope.research"}),
            allowed_tool_ids=frozenset({"documents.search"}),
            data_classification=DataClassification.INTERNAL,
        ),
        "budget": budget(max_tokens=40, max_cost=2, max_children=1, max_depth=2),
        "research_constraints": research_constraints(
            allowed_domains=frozenset({ResearchDomain.TECHNOLOGY}),
            allowed_source_categories=frozenset(
                {ResearchToolCategory.INTERNAL_DOCUMENT}
            ),
            data_classification_ceiling=DataClassification.INTERNAL,
        ),
    }
    values.update(changes)
    return ChildAuthorityRequest.model_validate(values)


def task(**changes: Any) -> ChildTaskSpec:
    values: dict[str, Any] = {
        "child_task_id": "child_task_technology_001",
        "goal": "Summarize the authorized technology evidence.",
        "input": {"question": "What is the platform risk?"},
        "expected_result_schema": {
            "type": "object",
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
            "additionalProperties": False,
        },
        "domain": ResearchDomain.TECHNOLOGY,
    }
    values.update(changes)
    return ChildTaskSpec.model_validate(values)


def intent(**changes: Any):  # type: ignore[no-untyped-def]
    planned = DelegationPlanner().plan(
        snapshot=snapshot(),
        target_agent_id="agent_technology",
        target_agent_version="1.0.0",
        capability_id="capability.research",
        task=task(),
        requested_authority=child_authority(),
    )
    changed = planned.model_copy(update=changes)
    return changed.model_copy(
        update={"delegation_key": expected_delegation_key(changed)}
    )


def evidence(**changes: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "tenant_id": "tenant_h6_001",
        "organization_id": "organization_h6_001",
        "workspace_id": "workspace_h6_001",
        "run_id": "run_child_h6_001",
        "correlation_id": "corr_h6_001",
        "scope_refs": ["scope.research"],
        "evidence_id": "evidence_child_h6_001",
        "source_id": "source_child_h6_001",
        "uri": "urn:alos:evidence:h6:1",
        "captured_at": "2026-09-22T09:00:00Z",
        "retrieved_at": "2026-09-22T09:00:00Z",
        "content_hash": "sha256:" + "a" * 64,
        "source_version": "1.0.0",
        "anchor": "section:1",
        "excerpt": "Validated child evidence.",
        "data_classification": "INTERNAL",
        "source_type": "INTERNAL",
        "freshness": "CURRENT",
        "reliability": "HIGH",
        "content_trust": "GOVERNED",
        "instruction_authority": False,
        "validation_status": "VALID",
    }
    values.update(changes)
    return values


def child_result(**changes: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "run_id": "run_child_h6_001",
        "root_run_id": "run_root_h6_001",
        "parent_run_id": "run_parent_h6_001",
        "correlation_id": "corr_h6_001",
        "agent_id": "agent_technology",
        "agent_version": "1.0.0",
        "capability_id": "capability.research",
        "status": "COMPLETED",
        "output_state": "AI_INFERRED",
        "output": {"summary": "Bounded child result."},
        "usage": {"input_tokens": 5, "output_tokens": 3},
        "evidence_refs": [evidence()],
        "tool_results": [],
        "started_at": "2026-09-22T09:00:00Z",
        "completed_at": "2026-09-22T09:01:00Z",
    }
    values.update(changes)
    return values


def validator() -> ChildResultValidator:
    return ChildResultValidator(CanonicalContractCatalog(CONTRACTS_ROOT))


def technology_target(**changes: Any) -> AuthorizedChildTarget:
    base = next(item for item in targets() if item.agent_id == "agent_technology")
    return base.model_copy(update=changes)


def test_planner_preserves_structured_task_and_exact_target() -> None:
    planned = intent()
    assert planned.target_agent_id == "agent_technology"
    assert planned.target_agent_version == "1.0.0"
    assert planned.task == task()
    assert planned.depth == 2
    assert planned.delegation_key == intent().delegation_key
    with pytest.raises(DelegationPlanningError, match="Exact"):
        DelegationPlanner().plan(
            snapshot=snapshot(),
            target_agent_id="agent_unknown",
            target_agent_version="9.9.9",
            capability_id="capability.research",
            task=task(),
            requested_authority=child_authority(),
        )


@pytest.mark.parametrize(
    ("change", "code"),
    (
        ({"root_run_id": "run_wrong"}, "DELEGATION_LINEAGE_MISMATCH"),
        ({"parent_run_id": "run_wrong"}, "DELEGATION_LINEAGE_MISMATCH"),
        ({"depth": 4}, "DELEGATION_DEPTH_EXCEEDED"),
        ({"target_agent_version": "2.0.0"}, "CHILD_TARGET_DENIED"),
        ({"target_capability_id": "capability.other"}, "CHILD_CAPABILITY_DENIED"),
    ),
)
def test_lineage_depth_target_and_capability_fail_closed(
    change: dict[str, Any], code: str
) -> None:
    with pytest.raises(DelegationDenied) as raised:
        DelegationGuard().validate(snapshot(), intent(**change))
    assert raised.value.code == code


@pytest.mark.parametrize(
    ("authority_change", "code"),
    (
        ({"tenant_id": "tenant_other"}, "CHILD_TENANT_MISMATCH"),
        ({"organization_id": "organization_other"}, "CHILD_ORGANIZATION_MISMATCH"),
        ({"workspace_id": "workspace_other"}, "CHILD_WORKSPACE_MISMATCH"),
        (
            {"permission_refs": frozenset({"research.read", "admin.write"})},
            "CHILD_PERMISSION_EXPANSION",
        ),
        ({"scope_refs": frozenset({"scope.other"})}, "CHILD_SCOPE_EXPANSION"),
        ({"allowed_tool_ids": frozenset({"tool.admin"})}, "CHILD_TOOL_EXPANSION"),
        (
            {"data_classification": DataClassification.RESTRICTED},
            "CHILD_CLASSIFICATION_EXPANSION",
        ),
    ),
)
def test_authority_must_only_narrow(authority_change: dict[str, Any], code: str) -> None:
    requested = child_authority(authority=authority(**authority_change))
    with pytest.raises(DelegationDenied) as raised:
        DelegationGuard().validate(snapshot(), intent(requested_authority=requested))
    assert raised.value.code == code


@pytest.mark.parametrize(
    ("budget_change", "code"),
    (
        ({"max_tokens": 101}, "CHILD_BUDGET_EXPANSION"),
        ({"max_cost": 6}, "CHILD_BUDGET_EXPANSION"),
        ({"timeout_seconds": 61}, "CHILD_BUDGET_EXPANSION"),
        ({"max_depth": 4}, "CHILD_BUDGET_EXPANSION"),
    ),
)
def test_child_budget_must_be_contained(budget_change: dict[str, Any], code: str) -> None:
    requested = child_authority(budget=budget(**budget_change))
    with pytest.raises(DelegationDenied) as raised:
        DelegationGuard().validate(snapshot(), intent(requested_authority=requested))
    assert raised.value.code == code


def test_duplicate_child_count_cycle_and_reservations_are_bounded() -> None:
    planned = intent()
    cases = (
        ({"submitted_keys": frozenset({planned.delegation_key})}, "DUPLICATE_DELEGATION"),
        ({"child_count": 2}, "DELEGATION_CHILD_LIMIT"),
        ({"reserved_tokens": 70}, "CHILD_TOKEN_RESERVATION_EXCEEDED"),
        ({"reserved_cost": 4}, "CHILD_COST_RESERVATION_EXCEEDED"),
    )
    for kwargs, code in cases:
        with pytest.raises(DelegationDenied) as raised:
            DelegationGuard().validate(snapshot(), planned, **kwargs)  # type: ignore[arg-type]
        assert raised.value.code == code
    cyclic = snapshot(
        allowed_child_targets=(
            AuthorizedChildTarget(
                agent_id="agent_parent_h6",
                agent_version="2.0.0",
                capability_ids=("capability.research",),
                research_domains=(ResearchDomain.TECHNOLOGY,),
            ),
        )
    )
    self_intent = DelegationPlanner().plan(
        snapshot=cyclic,
        target_agent_id="agent_parent_h6",
        target_agent_version="2.0.0",
        capability_id="capability.research",
        task=task(),
        requested_authority=child_authority(),
    )
    with pytest.raises(DelegationDenied, match="cycle"):
        DelegationGuard().validate(cyclic, self_intent)

    indirect = snapshot(ancestry_agent_refs=("agent_technology@1.0.0",))
    indirect_intent = DelegationPlanner().plan(
        snapshot=indirect,
        target_agent_id="agent_technology",
        target_agent_version="1.0.0",
        capability_id="capability.research",
        task=task(),
        requested_authority=child_authority(),
    )
    with pytest.raises(DelegationDenied, match="cycle"):
        DelegationGuard().validate(indirect, indirect_intent)


def test_tampered_delegation_key_is_rejected() -> None:
    tampered = intent().model_copy(update={"delegation_key": "sha256:" + "f" * 64})
    with pytest.raises(DelegationDenied) as raised:
        DelegationGuard().validate(snapshot(), tampered)
    assert raised.value.code == "DELEGATION_KEY_INVALID"


def test_different_material_task_has_different_key() -> None:
    assert intent().delegation_key != DelegationPlanner().plan(
        snapshot=snapshot(),
        target_agent_id="agent_technology",
        target_agent_version="1.0.0",
        capability_id="capability.research",
        task=task(child_task_id="child_task_technology_002", goal="Different goal"),
        requested_authority=child_authority(),
    ).delegation_key


@pytest.mark.parametrize(
    ("constraints", "code"),
    (
        (
            research_constraints(
                allowed_domains=frozenset({ResearchDomain.MANAGEMENT}),
                data_classification_ceiling=DataClassification.INTERNAL,
            ),
            "RESEARCH_DOMAIN_DENIED",
        ),
        (
            research_constraints(
                allowed_domains=frozenset({ResearchDomain.TECHNOLOGY}),
                allowed_source_categories=frozenset({ResearchToolCategory.CONNECTOR}),
            ),
            "RESEARCH_SOURCE_EXPANSION",
        ),
        (
            research_constraints(
                allowed_domains=frozenset({ResearchDomain.TECHNOLOGY}),
                external_research_allowed=True,
            ),
            "RESEARCH_EGRESS_EXPANSION",
        ),
    ),
)
def test_research_constraints_only_narrow(
    constraints: ResearchDelegationConstraints, code: str
) -> None:
    requested = child_authority(research_constraints=constraints)
    with pytest.raises(DelegationDenied) as raised:
        DelegationGuard().validate(snapshot(), intent(requested_authority=requested))
    assert raised.value.code == code


@pytest.mark.parametrize("domain", list(ResearchDomain))
def test_one_generic_policy_supports_all_research_domains(domain: ResearchDomain) -> None:
    request = DomainDelegationRequest(
        child_task_id=f"child_task_{domain.value.lower()}",
        domain=domain,
        goal=f"Research {domain.value}",
        input={"domain": domain.value},
        expected_result_schema={"type": "object"},
        authority=child_authority(
            research_constraints=research_constraints(
                allowed_domains=frozenset({domain}),
                allowed_source_categories=frozenset(
                    {ResearchToolCategory.INTERNAL_DOCUMENT}
                ),
                data_classification_ceiling=DataClassification.INTERNAL,
            )
        ),
        capability_id="capability.research",
    )
    result = ResearchDomainDelegationPolicy().plan(snapshot=snapshot(), request=request)
    assert result.task.domain is domain
    assert result.target_agent_id == f"agent_{domain.value.lower()}"


def test_same_mechanism_structurally_supports_bounded_sub_child() -> None:
    child_snapshot = snapshot(
        parent_run_id="run_child_h6_001",
        parent_agent_id="agent_technology",
        parent_agent_version="1.0.0",
        parent_depth=1,
        ancestry_agent_refs=("agent_parent_h6@2.0.0",),
        allowed_child_targets=(
            AuthorizedChildTarget(
                agent_id="agent_management",
                agent_version="1.0.0",
                capability_ids=("capability.research",),
                research_domains=(ResearchDomain.MANAGEMENT,),
            ),
        ),
    )
    child_task = task(
        child_task_id="child_task_management_001",
        domain=ResearchDomain.MANAGEMENT,
    )
    sub_child = DelegationPlanner().plan(
        snapshot=child_snapshot,
        target_agent_id="agent_management",
        target_agent_version="1.0.0",
        capability_id="capability.research",
        task=child_task,
        requested_authority=child_authority(
            research_constraints=research_constraints(
                allowed_domains=frozenset({ResearchDomain.MANAGEMENT}),
                allowed_source_categories=frozenset(
                    {ResearchToolCategory.INTERNAL_DOCUMENT}
                ),
                data_classification_ceiling=DataClassification.INTERNAL,
            )
        ),
    )
    DelegationGuard().validate(child_snapshot, sub_child)
    assert sub_child.depth == 2


def test_two_explicit_domains_create_distinct_bounded_tasks() -> None:
    policy = ResearchDomainDelegationPolicy()
    intents = tuple(
        policy.plan(
            snapshot=snapshot(),
            request=DomainDelegationRequest(
                child_task_id=f"child_task_{domain.value.lower()}",
                domain=domain,
                goal=f"Research {domain.value}",
                input={"domain": domain.value},
                expected_result_schema={"type": "object"},
                authority=child_authority(
                    research_constraints=research_constraints(
                        allowed_domains=frozenset({domain}),
                        allowed_source_categories=frozenset(
                            {ResearchToolCategory.INTERNAL_DOCUMENT}
                        ),
                        data_classification_ceiling=DataClassification.INTERNAL,
                    )
                ),
                capability_id="capability.research",
            ),
        )
        for domain in (ResearchDomain.TECHNOLOGY, ResearchDomain.PROPERTY_MARKET)
    )
    assert len({item.delegation_key for item in intents}) == 2


def test_canonical_child_result_identity_output_and_evidence_validate() -> None:
    observation = validator().validate(
        child_result(),
        intent=intent(),
        target=technology_target(),
        correlation_id="corr_h6_001",
        parent_authority=authority(),
    )
    assert observation.status == "COMPLETED"
    assert observation.evidence_refs[0]["correlation_id"] == "corr_h6_001"
    assert observation.usage == {"input_tokens": 5, "output_tokens": 3}


def test_external_child_evidence_remains_untrusted_and_non_instructional() -> None:
    external = evidence(source_type="EXTERNAL", content_trust="UNTRUSTED")
    observation = validator().validate(
        child_result(evidence_refs=[external]),
        intent=intent(),
        target=technology_target(),
        correlation_id="corr_h6_001",
        parent_authority=authority(),
    )
    assert observation.evidence_refs[0]["content_trust"] == "UNTRUSTED"
    assert observation.evidence_refs[0]["instruction_authority"] is False


@pytest.mark.parametrize("status", ("FAILED", "CANCELLED", "TIMED_OUT"))
def test_canonical_child_failure_statuses_are_structured(status: str) -> None:
    payload = child_result(
        status=status,
        output_state="BLOCKED",
        error={
            "code": f"CHILD_{status}",
            "message": "child stopped safely",
            "correlation_id": "corr_h6_001",
            "retryable": False,
        },
    )
    payload.pop("output")
    observation = validator().validate(
        payload,
        intent=intent(),
        target=technology_target(),
        correlation_id="corr_h6_001",
        parent_authority=authority(),
    )
    assert observation.status == status
    assert observation.validation_status == "VALID"


@pytest.mark.parametrize(
    ("change", "code"),
    (
        ({"root_run_id": "run_wrong"}, "CHILD_RESULT_IDENTITY_MISMATCH"),
        ({"parent_run_id": "run_wrong"}, "CHILD_RESULT_IDENTITY_MISMATCH"),
        ({"correlation_id": "corr_wrong"}, "CHILD_RESULT_IDENTITY_MISMATCH"),
        ({"agent_id": "agent_wrong"}, "CHILD_RESULT_IDENTITY_MISMATCH"),
        ({"agent_version": "2.0.0"}, "CHILD_RESULT_IDENTITY_MISMATCH"),
        ({"capability_id": "capability.other"}, "CHILD_RESULT_CAPABILITY_MISMATCH"),
        ({"output": {"wrong": True}}, "CHILD_OUTPUT_SCHEMA_INVALID"),
    ),
)
def test_child_result_mismatch_fails_closed(change: dict[str, Any], code: str) -> None:
    with pytest.raises(ChildResultInvalid) as raised:
        validator().validate(
            child_result(**change),
            intent=intent(),
            target=technology_target(),
            correlation_id="corr_h6_001",
            parent_authority=authority(),
        )
    assert raised.value.code == code


@pytest.mark.parametrize(
    "evidence_change",
    (
        {"scope_refs": ["scope.other"]},
        {"data_classification": "RESTRICTED"},
        {"freshness": "STALE"},
        {"validation_status": "INVALID"},
        {"source_type": "EXTERNAL", "content_trust": "GOVERNED"},
        {"instruction_authority": True},
    ),
)
def test_invalid_child_evidence_never_enters_parent(evidence_change: dict[str, Any]) -> None:
    with pytest.raises((ChildResultInvalid, ValueError)):
        validator().validate(
            child_result(evidence_refs=[evidence(**evidence_change)]),
            intent=intent(),
            target=technology_target(),
            correlation_id="corr_h6_001",
            parent_authority=authority(),
        )


@pytest.mark.parametrize(
    ("target_change", "task_change", "code"),
    (
        ({}, {"expected_result_schema": {"type": "not-a-json-type"}}, "CHILD_TASK_SCHEMA_INVALID"),
        (
            {"input_schema": {"type": "not-a-json-type"}},
            {},
            "CHILD_TARGET_INPUT_SCHEMA_INVALID",
        ),
        (
            {"output_schema": {"type": "not-a-json-type"}},
            {},
            "CHILD_TARGET_OUTPUT_SCHEMA_INVALID",
        ),
        (
            {
                "input_schema": {
                    "type": "object",
                    "required": ["authorized"],
                    "properties": {"authorized": {"const": True}},
                }
            },
            {},
            "CHILD_INPUT_INVALID",
        ),
    ),
)
def test_child_task_and_target_schema_preflight(
    target_change: dict[str, Any], task_change: dict[str, Any], code: str
) -> None:
    target = technology_target(**target_change)
    with pytest.raises(DelegationPlanningError) as raised:
        DelegationPlanner.validate_task(target, task(**task_change))
    assert raised.value.code == code


def test_child_output_must_satisfy_exact_target_schema() -> None:
    target = technology_target(
        output_schema={
            "type": "object",
            "required": ["summary", "confidence"],
            "properties": {
                "summary": {"type": "string"},
                "confidence": {"type": "number"},
            },
        }
    )
    with pytest.raises(ChildResultInvalid) as raised:
        validator().validate(
            child_result(),
            intent=intent(),
            target=target,
            correlation_id="corr_h6_001",
            parent_authority=authority(),
        )
    assert raised.value.code == "CHILD_OUTPUT_TARGET_SCHEMA_INVALID"


def test_child_output_satisfying_task_and_target_schemas_is_accepted() -> None:
    target = technology_target(
        output_schema={
            "type": "object",
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
        }
    )
    observation = validator().validate(
        child_result(),
        intent=intent(),
        target=target,
        correlation_id="corr_h6_001",
        parent_authority=authority(),
    )
    assert observation.validation_status == "VALID"


def test_invalid_target_output_schema_fails_closed_during_result_validation() -> None:
    with pytest.raises(ChildResultInvalid) as raised:
        validator().validate(
            child_result(),
            intent=intent(),
            target=technology_target(output_schema={"type": "not-a-json-type"}),
            correlation_id="corr_h6_001",
            parent_authority=authority(),
        )
    assert raised.value.code == "CHILD_TARGET_OUTPUT_SCHEMA_INVALID"


@pytest.mark.parametrize(
    "changes",
    (
        {
            "allowed_source_categories": frozenset(
                {ResearchToolCategory.EXTERNAL_RESEARCH}
            )
        },
        {"maximum_external_cost": 1},
    ),
)
def test_disabled_external_research_constraints_reject_contradictions(
    changes: dict[str, Any],
) -> None:
    with pytest.raises(ValueError):
        research_constraints(**changes)


def test_external_research_constraints_accept_explicit_enabled_policy() -> None:
    constraints = research_constraints(
        external_research_allowed=True,
        maximum_external_cost=1,
        allowed_source_categories=frozenset(
            {
                ResearchToolCategory.INTERNAL_DOCUMENT,
                ResearchToolCategory.EXTERNAL_RESEARCH,
            }
        ),
    )
    assert constraints.external_research_allowed is True


def observation(task_id: str, status: str, *, valid: bool = True) -> ChildObservation:
    return ChildObservation(
        child_task_id=task_id,
        delegation_key="sha256:" + ("a" if task_id.endswith("a") else "b") * 64,
        target_agent_id="agent_child",
        target_agent_version="1.0.0",
        target_capability_id="capability.research",
        run_id=f"run_{task_id}",
        status=status,
        validation_status="VALID" if valid else "INVALID",
        output={"summary": task_id} if status == "COMPLETED" else None,
        evidence_refs=(evidence(evidence_id=f"evidence_{task_id}"),)
        if status == "COMPLETED"
        else (),
        error_code=None if status == "COMPLETED" else "CHILD_FAILED",
    )


def test_synthesis_is_deterministic_partial_and_preserves_success() -> None:
    success = observation("task_a", "COMPLETED")
    failed = observation("task_b", "FAILED")
    synthesis = DelegationSynthesizer().synthesize((success, failed))
    assert synthesis.disposition is DelegationDisposition.PARTIAL
    assert synthesis.successful_children == (success,)
    assert synthesis.failed_children == (failed,)
    assert synthesis.evidence_refs[0]["evidence_id"] == "evidence_task_a"
    assert synthesis == DelegationSynthesizer().synthesize((success, failed))


def test_synthesis_marks_invalid_only_result_for_review() -> None:
    result = DelegationSynthesizer().synthesize(
        (observation("task_a", "FAILED", valid=False),)
    )
    assert result.disposition is DelegationDisposition.NEEDS_REVIEW
    assert result.evidence_refs == ()
