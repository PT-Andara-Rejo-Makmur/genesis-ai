"""Conservative policy for proposing durable memory to Backend governance."""

from __future__ import annotations

import re

from genesis.memory.models import (
    MemoryWriteDecision,
    MemoryWriteDisposition,
    MemoryWriteInput,
    MemoryWriteProposal,
)
from genesis.research.models import FindingKind
from genesis.runtime.context.models import DataClassification

_PROPOSABLE_STATES = frozenset({"VALIDATED", "VERIFIED", "APPROVED"})
_REVIEW_STATES = frozenset({"AI_INFERRED", "NEEDS_REVIEW", "DRAFT"})
_REJECTED_STATES = frozenset({"FAILED", "BLOCKED", "REJECTED", "STALE", "CONFLICTED", "CANCELLED"})
_SECRET_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]",
        r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    )
)
_SECRET_METADATA_KEYS = frozenset(
    {"api_key", "access_token", "refresh_token", "password", "secret", "credential"}
)
_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}


class MemoryWritePolicy:
    """Returns a proposal decision only and has no persistence dependency."""

    def evaluate(self, item: MemoryWriteInput) -> MemoryWriteDecision:
        reasons: list[str] = []
        content = " ".join(item.content.split())
        state = item.output_state.upper()

        if not content:
            reasons.append("CONTENT_REQUIRED")
        if state in _REJECTED_STATES:
            reasons.append("OUTPUT_STATE_REJECTED")
        elif state not in _PROPOSABLE_STATES and state not in _REVIEW_STATES:
            reasons.append("OUTPUT_STATE_UNKNOWN")
        if not item.reusable:
            reasons.append("CONTENT_NOT_REUSABLE")
        if not set(item.scope_refs).issubset(item.execution_context.scope_refs):
            reasons.append("SCOPE_EXPANSION")
        if item.data_classification is not item.execution_context.data_classification:
            reasons.append("CLASSIFICATION_NOT_EXACT")
        if not item.evidence_refs:
            reasons.append("LINEAGE_REQUIRED")
        if item.finding_kind is FindingKind.RESEARCH and item.domain is None:
            reasons.append("RESEARCH_DOMAIN_REQUIRED")
        if item.originating_correlation_id != item.execution_context.correlation_id:
            reasons.append("ORIGIN_CORRELATION_MISMATCH")
        if any(pattern.search(content) for pattern in _SECRET_PATTERNS) or any(
            str(key).casefold() in _SECRET_METADATA_KEYS for key in item.metadata
        ):
            reasons.append("SENSITIVE_RUNTIME_SECRET")
        if any(
            evidence.tenant_id != item.execution_context.tenant_id
            or evidence.organization_id != item.execution_context.organization_id
            or evidence.workspace_id != item.execution_context.workspace_id
            or evidence.run_id != item.originating_run_id
            or evidence.correlation_id != item.originating_correlation_id
            or evidence.validation_status != "VALID"
            or evidence.freshness != "CURRENT"
            or not set(evidence.scope_refs).issubset(item.scope_refs)
            or not set(evidence.scope_refs).issubset(item.execution_context.scope_refs)
            or _CLASSIFICATION_RANK[evidence.data_classification]
            > _CLASSIFICATION_RANK[item.data_classification]
            for evidence in item.evidence_refs
        ):
            reasons.append("EVIDENCE_LINEAGE_INVALID")

        if reasons:
            return MemoryWriteDecision(
                disposition=MemoryWriteDisposition.REJECT,
                reason_codes=tuple(dict.fromkeys(reasons)),
            )
        proposal = MemoryWriteProposal(
            content=content,
            tenant_id=item.execution_context.tenant_id,
            organization_id=item.execution_context.organization_id,
            workspace_id=item.execution_context.workspace_id,
            scope_refs=item.scope_refs,
            data_classification=item.data_classification,
            evidence_refs=item.evidence_refs,
            originating_run_id=item.originating_run_id,
            originating_correlation_id=item.originating_correlation_id,
            domain=item.domain,
            finding_kind=item.finding_kind,
        )
        if state in _REVIEW_STATES:
            return MemoryWriteDecision(
                disposition=MemoryWriteDisposition.REVIEW_REQUIRED,
                reason_codes=("HUMAN_REVIEW_REQUIRED", "NO_SELF_APPROVAL"),
                proposal=proposal,
            )
        return MemoryWriteDecision(
            disposition=MemoryWriteDisposition.PROPOSE,
            reason_codes=("DURABLE_MEMORY_CANDIDATE", "BACKEND_APPROVAL_REQUIRED"),
            proposal=proposal,
        )
