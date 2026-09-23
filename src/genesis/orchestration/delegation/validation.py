"""Canonical child-result and evidence validation before parent consumption."""

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from genesis.contracts import CanonicalContractCatalog, ContractValidationError
from genesis.orchestration.delegation.models import (
    AuthorityEnvelope,
    AuthorizedChildTarget,
    ChildObservation,
    DelegationIntent,
)
from genesis.runtime.context import DataClassification

AGENT_RUN_RESULT_SCHEMA = "https://schemas.alos.dev/v1/agent/agent-run-result.schema.json"
_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC.value: 0,
    DataClassification.INTERNAL.value: 1,
    DataClassification.CONFIDENTIAL.value: 2,
    DataClassification.RESTRICTED.value: 3,
}


class ChildResultInvalid(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ChildResultValidator:
    def __init__(self, contracts: CanonicalContractCatalog) -> None:
        self._contracts = contracts

    def validate(
        self,
        payload: dict[str, Any],
        *,
        intent: DelegationIntent,
        target: AuthorizedChildTarget,
        correlation_id: str,
        parent_authority: AuthorityEnvelope,
    ) -> ChildObservation:
        try:
            result = self._contracts.validate(AGENT_RUN_RESULT_SCHEMA, payload)
        except ContractValidationError as exc:
            raise ChildResultInvalid("CHILD_RESULT_CONTRACT_INVALID", str(exc)) from exc
        expected = {
            "root_run_id": intent.root_run_id,
            "parent_run_id": intent.parent_run_id,
            "correlation_id": correlation_id,
            "agent_id": intent.target_agent_id,
            "agent_version": intent.target_agent_version,
        }
        if any(result.get(key) != value for key, value in expected.items()):
            raise ChildResultInvalid("CHILD_RESULT_IDENTITY_MISMATCH", "Child identity mismatch")
        if result.get("capability_id") not in {None, intent.target_capability_id}:
            raise ChildResultInvalid("CHILD_RESULT_CAPABILITY_MISMATCH", "Capability mismatch")
        if result["status"] == "COMPLETED":
            try:
                Draft202012Validator.check_schema(intent.task.expected_result_schema)
            except SchemaError as exc:
                raise ChildResultInvalid(
                    "CHILD_TASK_SCHEMA_INVALID", "Expected result schema is invalid"
                ) from exc
            errors = list(
                Draft202012Validator(intent.task.expected_result_schema).iter_errors(
                    result.get("output")
                )
            )
            if errors:
                raise ChildResultInvalid("CHILD_OUTPUT_SCHEMA_INVALID", "Child output invalid")
            if target.output_schema is not None:
                try:
                    Draft202012Validator.check_schema(target.output_schema)
                except SchemaError as exc:
                    raise ChildResultInvalid(
                        "CHILD_TARGET_OUTPUT_SCHEMA_INVALID",
                        "Target output schema is invalid",
                    ) from exc
                target_errors = list(
                    Draft202012Validator(target.output_schema).iter_errors(result.get("output"))
                )
                if target_errors:
                    raise ChildResultInvalid(
                        "CHILD_OUTPUT_TARGET_SCHEMA_INVALID",
                        "Child output violates the exact target schema",
                    )
        evidence = tuple(result.get("evidence_refs", []))
        for item in evidence:
            self._validate_evidence(item, parent_authority)
            self._validate_evidence(item, intent.requested_authority.authority)
        return ChildObservation(
            child_task_id=intent.task.child_task_id,
            delegation_key=intent.delegation_key,
            target_agent_id=intent.target_agent_id,
            target_agent_version=intent.target_agent_version,
            target_capability_id=intent.target_capability_id,
            run_id=result["run_id"],
            status=result["status"],
            validation_status="VALID",
            output=result.get("output"),
            evidence_refs=evidence,
            usage=result.get("usage"),
            error_code=(result.get("error") or {}).get("code"),
        )

    @staticmethod
    def invalid_observation(intent: DelegationIntent, code: str) -> ChildObservation:
        return ChildObservation(
            child_task_id=intent.task.child_task_id,
            delegation_key=intent.delegation_key,
            target_agent_id=intent.target_agent_id,
            target_agent_version=intent.target_agent_version,
            target_capability_id=intent.target_capability_id,
            status="FAILED",
            validation_status="INVALID",
            error_code=code,
        )

    @staticmethod
    def _validate_evidence(item: dict[str, Any], parent: AuthorityEnvelope) -> None:
        if (
            item.get("tenant_id") != parent.tenant_id
            or item.get("organization_id") != parent.organization_id
            or item.get("workspace_id") != parent.workspace_id
        ):
            raise ChildResultInvalid("CHILD_EVIDENCE_IDENTITY_MISMATCH", "Evidence identity")
        if not set(item.get("scope_refs", [])).issubset(parent.scope_refs):
            raise ChildResultInvalid("CHILD_EVIDENCE_SCOPE_MISMATCH", "Evidence scope")
        classification = item.get("data_classification")
        if (
            classification not in _CLASSIFICATION_RANK
            or _CLASSIFICATION_RANK[classification]
            > _CLASSIFICATION_RANK[parent.data_classification.value]
        ):
            raise ChildResultInvalid("CHILD_EVIDENCE_CLASSIFICATION", "Evidence classification")
        if item.get("validation_status") != "VALID" or item.get("freshness") != "CURRENT":
            raise ChildResultInvalid("CHILD_EVIDENCE_INVALID", "Evidence is stale or invalid")
        if item.get("instruction_authority") is not False:
            raise ChildResultInvalid("CHILD_EVIDENCE_AUTHORITY", "Evidence cannot instruct")
        if item.get("source_type") == "EXTERNAL" and item.get("content_trust") != "UNTRUSTED":
            raise ChildResultInvalid("CHILD_EVIDENCE_TRUST", "External evidence must be untrusted")
