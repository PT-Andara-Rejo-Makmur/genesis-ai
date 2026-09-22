"""Deterministic structured child-task planning over exact authorized targets."""

import hashlib
import json
from enum import Enum
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from genesis.orchestration.delegation.models import (
    AuthorizedChildTarget,
    ChildAuthorityRequest,
    ChildTaskSpec,
    DelegationAuthorizationSnapshot,
    DelegationIntent,
    DomainDelegationRequest,
)


class DelegationPlanningError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in sorted(value.items())}
    if isinstance(value, (set, frozenset)):
        normalized = (_normalize(item) for item in value)
        return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def delegation_key(fields: dict[str, object]) -> str:
    canonical = json.dumps(_normalize(fields), sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def expected_delegation_key(intent: DelegationIntent) -> str:
    return delegation_key(intent.model_dump(mode="python", exclude={"delegation_key"}))


class DelegationPlanner:
    """Build an intent without granting authority or minting a child run."""

    def plan(
        self,
        *,
        snapshot: DelegationAuthorizationSnapshot,
        target_agent_id: str,
        target_agent_version: str,
        capability_id: str,
        task: ChildTaskSpec,
        requested_authority: ChildAuthorityRequest,
    ) -> DelegationIntent:
        target = self._exact_target(
            snapshot, target_agent_id, target_agent_version, capability_id
        )
        if task.domain is not None and task.domain not in target.research_domains:
            raise DelegationPlanningError(
                "RESEARCH_DOMAIN_DENIED",
                "Authorized child target does not support task domain",
            )
        self.validate_task(target, task)
        ancestry = (*snapshot.ancestry_agent_refs, self._parent_ref(snapshot))
        fields = {
            "parent_run_id": snapshot.parent_run_id,
            "root_run_id": snapshot.root_run_id,
            "parent_agent_id": snapshot.parent_agent_id,
            "parent_agent_version": snapshot.parent_agent_version,
            "target_agent_id": target.agent_id,
            "target_agent_version": target.agent_version,
            "target_capability_id": capability_id,
            "depth": snapshot.parent_depth + 1,
            "ancestry_agent_refs": ancestry,
            "task": task.model_dump(mode="python"),
            "requested_authority": requested_authority.model_dump(mode="python"),
        }
        return DelegationIntent.model_validate(
            {**fields, "delegation_key": delegation_key(fields)}
        )

    @staticmethod
    def _exact_target(
        snapshot: DelegationAuthorizationSnapshot,
        agent_id: str,
        agent_version: str,
        capability_id: str,
    ) -> AuthorizedChildTarget:
        target = next(
            (
                item
                for item in snapshot.allowed_child_targets
                if item.agent_id == agent_id and item.agent_version == agent_version
            ),
            None,
        )
        if target is None:
            raise DelegationPlanningError(
                "CHILD_TARGET_DENIED", "Exact child target is not authorized"
            )
        if capability_id not in target.capability_ids:
            raise DelegationPlanningError(
                "CHILD_CAPABILITY_DENIED", "Child capability is not authorized"
            )
        return target

    @classmethod
    def validate_intent_task(
        cls,
        snapshot: DelegationAuthorizationSnapshot,
        intent: DelegationIntent,
    ) -> AuthorizedChildTarget:
        target = cls._exact_target(
            snapshot,
            intent.target_agent_id,
            intent.target_agent_version,
            intent.target_capability_id,
        )
        if intent.task.domain is not None and intent.task.domain not in target.research_domains:
            raise DelegationPlanningError(
                "RESEARCH_DOMAIN_DENIED", "Child target does not support task domain"
            )
        cls.validate_task(target, intent.task)
        return target

    @staticmethod
    def validate_task(target: AuthorizedChildTarget, task: ChildTaskSpec) -> None:
        try:
            Draft202012Validator.check_schema(task.expected_result_schema)
        except SchemaError as exc:
            raise DelegationPlanningError(
                "CHILD_TASK_SCHEMA_INVALID", "Expected result schema is invalid"
            ) from exc
        if target.input_schema is not None:
            try:
                Draft202012Validator.check_schema(target.input_schema)
            except SchemaError as exc:
                raise DelegationPlanningError(
                    "CHILD_TARGET_INPUT_SCHEMA_INVALID", "Target input schema is invalid"
                ) from exc
            if list(Draft202012Validator(target.input_schema).iter_errors(task.input)):
                raise DelegationPlanningError(
                    "CHILD_INPUT_INVALID", "Child task input violates target schema"
                )
        if target.output_schema is not None:
            try:
                Draft202012Validator.check_schema(target.output_schema)
            except SchemaError as exc:
                raise DelegationPlanningError(
                    "CHILD_TARGET_OUTPUT_SCHEMA_INVALID", "Target output schema is invalid"
                ) from exc

    @staticmethod
    def _parent_ref(snapshot: DelegationAuthorizationSnapshot) -> str:
        return f"{snapshot.parent_agent_id}@{snapshot.parent_agent_version}"


class ResearchDomainDelegationPolicy:
    """One generic policy for all explicit R&D domain child tasks."""

    def __init__(self, planner: DelegationPlanner | None = None) -> None:
        self._planner = planner or DelegationPlanner()

    def plan(
        self,
        *,
        snapshot: DelegationAuthorizationSnapshot,
        request: DomainDelegationRequest,
    ) -> DelegationIntent:
        target = next(
            (
                item
                for item in snapshot.allowed_child_targets
                if request.domain in item.research_domains
                and request.capability_id in item.capability_ids
            ),
            None,
        )
        if target is None:
            raise DelegationPlanningError(
                "CHILD_TARGET_DENIED", "No exact authorized target supports the domain"
            )
        task = ChildTaskSpec(
            child_task_id=request.child_task_id,
            goal=request.goal,
            input=request.input,
            expected_result_schema=request.expected_result_schema,
            domain=request.domain,
        )
        return self._planner.plan(
            snapshot=snapshot,
            target_agent_id=target.agent_id,
            target_agent_version=target.agent_version,
            capability_id=request.capability_id,
            task=task,
            requested_authority=request.authority,
        )
