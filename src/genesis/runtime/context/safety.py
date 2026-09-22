"""Fail-closed tenant, scope, classification, and untrusted-content guards."""

from __future__ import annotations

import re
from collections.abc import Sequence

from genesis.runtime.context.models import (
    BackendContextAuthorization,
    ContextFailure,
    ContextSegment,
    ContextSource,
    DataClassification,
    ExecutionContextView,
    Freshness,
)

_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}
_INJECTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+(all\s+)?(previous|prior|system)\s+instructions?",
        r"override\s+(backend|system|authority|permission|scope)",
        r"grant\s+(me\s+)?(permission|role|access)",
        r"reveal\s+(the\s+)?system\s+prompt",
        r"execute\s+(this\s+)?(command|tool|instruction)",
    )
)


class ContextSafetyGuard:
    def validate_execution_context(
        self,
        context: ExecutionContextView,
        boundary: BackendContextAuthorization,
    ) -> None:
        correlation_id = context.correlation_id
        identity = {
            "tenant_id": (context.tenant_id, boundary.tenant_id),
            "organization_id": (context.organization_id, boundary.organization_id),
            "workspace_id": (context.workspace_id, boundary.workspace_id),
            "actor_id": (context.actor_id, boundary.actor_id),
        }
        mismatches = sorted(key for key, values in identity.items() if values[0] != values[1])
        if mismatches:
            raise ContextFailure(
                "CONTEXT_IDENTITY_MISMATCH",
                "ExecutionContext identity is outside the Backend authorization boundary.",
                correlation_id,
                details={"fields": mismatches},
            )
        if not context.scope_refs:
            raise ContextFailure(
                "CONTEXT_SCOPE_REQUIRED",
                "ExecutionContext requires at least one authorized scope.",
                correlation_id,
            )
        self._require_subset(
            "scope",
            context.scope_refs,
            boundary.allowed_scope_refs,
            correlation_id,
        )
        self._require_subset(
            "permission",
            context.permission_refs,
            boundary.allowed_permission_refs,
            correlation_id,
        )
        self._require_subset(
            "tool",
            context.allowed_tool_ids,
            boundary.allowed_tool_ids,
            correlation_id,
        )
        roles = tuple(
            dict.fromkeys(
                (context.authority_context.role, *context.authority_context.role_refs)
            )
        )
        self._require_subset("role", roles, boundary.allowed_role_refs, correlation_id)
        if context.authority_context.authority_level not in boundary.allowed_authority_levels:
            raise ContextFailure(
                "CONTEXT_AUTHORITY_DENIED",
                "ExecutionContext authority level is not authorized by Backend.",
                correlation_id,
            )
        if context.data_classification not in boundary.allowed_classifications:
            raise ContextFailure(
                "CONTEXT_CLASSIFICATION_DENIED",
                "ExecutionContext classification is not authorized by Backend.",
                correlation_id,
            )

    def validate_segments(
        self,
        segments: Sequence[ContextSegment],
        context: ExecutionContextView,
        boundary: BackendContextAuthorization,
        *,
        active_scope_refs: Sequence[str],
    ) -> None:
        for item in segments:
            self._require_subset(
                "scope", item.scope_refs, active_scope_refs, context.correlation_id
            )
            self._require_subset(
                "permission",
                item.permission_refs,
                context.permission_refs,
                context.correlation_id,
            )
            self._require_subset(
                "tool", item.tool_ids, boundary.allowed_tool_ids, context.correlation_id
            )
            if item.data_classification not in boundary.allowed_classifications or (
                _CLASSIFICATION_RANK[item.data_classification]
                > _CLASSIFICATION_RANK[context.data_classification]
            ):
                raise ContextFailure(
                    "CONTEXT_CLASSIFICATION_DENIED",
                    "Context segment classification exceeds the authorized execution context.",
                    context.correlation_id,
                    details={"segment_id": item.segment_id},
                )
            for evidence in item.all_evidence:
                if (
                    evidence.tenant_id != context.tenant_id
                    or evidence.organization_id != context.organization_id
                    or evidence.workspace_id != context.workspace_id
                ):
                    raise ContextFailure(
                        "CONTEXT_EVIDENCE_SCOPE_MISMATCH",
                        "Evidence identity does not match ExecutionContext.",
                        context.correlation_id,
                        details={"segment_id": item.segment_id},
                    )
                self._require_subset(
                    "evidence_scope",
                    evidence.scope_refs,
                    item.scope_refs,
                    context.correlation_id,
                )
                if (
                    item.source is not ContextSource.MEMORY
                    and evidence.correlation_id != context.correlation_id
                ):
                    raise ContextFailure(
                        "CONTEXT_EVIDENCE_CORRELATION_MISMATCH",
                        "Evidence correlation does not match ExecutionContext.",
                        context.correlation_id,
                        details={"segment_id": item.segment_id},
                    )
                if evidence.data_classification is not item.data_classification:
                    raise ContextFailure(
                        "CONTEXT_EVIDENCE_CLASSIFICATION_MISMATCH",
                        "Evidence and context segment classification do not match.",
                        context.correlation_id,
                        details={"segment_id": item.segment_id},
                    )
                if (
                    item.source is not ContextSource.MEMORY
                    and evidence.source_type != item.source.value
                ):
                    raise ContextFailure(
                        "CONTEXT_EVIDENCE_SOURCE_MISMATCH",
                        "Evidence source semantics do not match the context segment.",
                        context.correlation_id,
                        details={"segment_id": item.segment_id},
                    )
                if (
                    item.source is not ContextSource.MEMORY
                    and evidence.content_trust != item.trust.value
                ):
                    raise ContextFailure(
                        "CONTEXT_EVIDENCE_TRUST_MISMATCH",
                        "Evidence trust semantics do not match the context segment.",
                        context.correlation_id,
                        details={"segment_id": item.segment_id},
                    )
                if evidence.freshness != item.freshness.value:
                    raise ContextFailure(
                        "CONTEXT_EVIDENCE_FRESHNESS_MISMATCH",
                        "Evidence freshness does not match the context segment.",
                        context.correlation_id,
                        details={"segment_id": item.segment_id},
                    )
                if evidence.validation_status != "VALID":
                    raise ContextFailure(
                        "CONTEXT_EVIDENCE_INVALID",
                        "Context evidence must be validated by the governed boundary.",
                        context.correlation_id,
                        details={"segment_id": item.segment_id},
                    )
            if item.required and item.freshness is not Freshness.CURRENT:
                raise ContextFailure(
                    "CONTEXT_EVIDENCE_STALE",
                    "Required business context or authoritative evidence is not current.",
                    context.correlation_id,
                    details={"segment_id": item.segment_id},
                )
            has_external_origin = any(
                evidence.source_type == "EXTERNAL" for evidence in item.all_evidence
            )
            if has_external_origin and item.trust.value != "UNTRUSTED":
                raise ContextFailure(
                    "CONTEXT_EVIDENCE_TRUST_MISMATCH",
                    "External-origin memory must remain untrusted.",
                    context.correlation_id,
                    details={"segment_id": item.segment_id},
                )
            if (
                item.source is ContextSource.MEMORY
                and not has_external_origin
                and item.trust.value != "GOVERNED"
            ):
                raise ContextFailure(
                    "CONTEXT_EVIDENCE_TRUST_MISMATCH",
                    "Internal-origin memory must preserve governed trust.",
                    context.correlation_id,
                    details={"segment_id": item.segment_id},
                )
            if (item.source is ContextSource.EXTERNAL or has_external_origin) and any(
                pattern.search(item.content) for pattern in _INJECTION_PATTERNS
            ):
                raise ContextFailure(
                    "EXTERNAL_CONTEXT_INSTRUCTION_INJECTION",
                    "External content attempted to act as an instruction and was rejected.",
                    context.correlation_id,
                    details={"segment_id": item.segment_id},
                )

    @staticmethod
    def _require_subset(
        kind: str,
        requested: Sequence[str],
        authorized: Sequence[str],
        correlation_id: str,
    ) -> None:
        excess = sorted(set(requested).difference(authorized))
        if excess:
            raise ContextFailure(
                f"CONTEXT_{kind.upper()}_ESCALATION",
                f"Context attempted to expand Backend-authorized {kind}.",
                correlation_id,
                details={f"unauthorized_{kind}_refs": excess},
            )
