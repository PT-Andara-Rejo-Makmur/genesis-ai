"""Capability-first requirement understanding adapted from MVP-1 intelligence."""

from __future__ import annotations

import re
from collections.abc import Sequence

from genesis.capabilities.models.definition import CapabilityType
from genesis.capabilities.resolver.models import (
    CapabilityCatalogItem,
    CapabilityResolution,
    Requirement,
    RequirementUnderstanding,
    RiskLevel,
)

_CAPABILITY_HINTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("task", "tugas", "overdue", "terlambat"), ("task.list", "task.read")),
    (("finding", "temuan", "risk", "risiko", "gap"), ("finding.create",)),
    (
        ("document", "dokumen", "contract", "kontrak", "policy"),
        ("document.search", "document.read"),
    ),
    (("compare", "banding", "conflict", "konflik"), ("document.compare",)),
    (("project", "proyek"), ("project.list", "project.read")),
    (("report", "laporan", "brief"), ("report.generate",)),
    (("approval", "persetujuan"), ("approval.request",)),
)

_DOMAIN_HINTS: dict[str, tuple[str, ...]] = {
    "finance": ("finance", "keuangan", "budget", "biaya"),
    "property": ("property", "properti", "tenant", "lease"),
    "hr": ("hr", "sdm", "employee", "karyawan"),
    "legal": ("legal", "hukum", "contract", "kontrak"),
    "technology": ("technology", "teknologi", "software", "system", "sistem"),
    "sales": ("sales", "marketing", "penjualan", "pemasaran"),
}


class CapabilityResolver:
    """Resolve against a Backend-supplied catalog; never mutate registry state."""

    def resolve(
        self,
        requirement: Requirement,
        catalog: Sequence[CapabilityCatalogItem],
    ) -> CapabilityResolution:
        understanding = self.understand(requirement)
        requested = set(understanding.candidate_capability_ids)
        terms = set(self._tokens(understanding.normalized_intent))
        ranked: list[tuple[int, CapabilityCatalogItem]] = []
        for item in catalog:
            searchable = " ".join(
                (item.capability_id, item.name, item.purpose, *item.keywords)
            ).casefold()
            score = sum(1 for term in terms if term in searchable)
            if item.capability_id in requested:
                score += 100
            if score:
                ranked.append((score, item))
        resolved = tuple(
            item
            for _, item in sorted(
                ranked,
                key=lambda pair: (-pair[0], pair[1].capability_id),
            )
        )
        found_ids = {item.capability_id for item in resolved}
        missing = tuple(sorted(requested.difference(found_ids)))
        unavailable = any(
            item.availability != "AVAILABLE"
            or item.configuration_status not in {"CONFIGURED", "NOT_APPLICABLE"}
            for item in resolved
        )
        tools = tuple(
            dict.fromkeys(tool_id for item in resolved for tool_id in item.backing_tool_ids)
        )
        permissions = tuple(
            dict.fromkeys(permission for item in resolved for permission in item.permission_refs)
        )
        return CapabilityResolution(
            understanding=understanding,
            resolved=resolved,
            missing_capability_ids=missing,
            required_tool_ids=tools,
            required_permission_refs=permissions,
            activation_readiness=(
                "NEEDS_CONFIGURATION" if missing or unavailable else "READY_FOR_DRAFT"
            ),
        )

    def understand(self, requirement: Requirement) -> RequirementUnderstanding:
        normalized = " ".join(requirement.statement.casefold().split())
        candidates: list[str] = []
        for words, capability_ids in _CAPABILITY_HINTS:
            if any(word in normalized for word in words):
                candidates.extend(capability_ids)
        if not candidates:
            candidates.extend(("global.search", "organization.context.read"))
        domains = tuple(
            domain
            for domain, words in _DOMAIN_HINTS.items()
            if any(word in normalized for word in words)
        ) or ("general",)
        recommended_type = requirement.preferred_capability_type or self._classify_type(
            normalized, len(set(candidates))
        )
        requires_agent = recommended_type in {
            CapabilityType.AGENT,
            CapabilityType.COMPOSITE,
        }
        risk = self._risk(normalized, candidates)
        rationale = [
            f"Matched {len(set(candidates))} capability intent(s).",
            f"Classified delivery as {recommended_type.value}.",
        ]
        if not requires_agent:
            rationale.append("Capability-first policy does not require an Agent runtime.")
        return RequirementUnderstanding(
            normalized_intent=normalized,
            domains=domains,
            candidate_capability_ids=tuple(dict.fromkeys(candidates)),
            recommended_type=recommended_type,
            risk_level=risk,
            requires_agent=requires_agent,
            rationale=tuple(rationale),
        )

    @staticmethod
    def _classify_type(statement: str, candidate_count: int) -> CapabilityType:
        if any(word in statement for word in ("agent", "assistant", "koordinator")):
            return CapabilityType.AGENT
        if any(word in statement for word in ("workflow", "alur", "proses")):
            return CapabilityType.WORKFLOW
        if any(word in statement for word in ("validate", "validasi", "checker")):
            return CapabilityType.VALIDATOR
        if any(word in statement for word in ("schedule", "jadwal", "monitor")):
            return CapabilityType.SCHEDULE
        if any(word in statement for word in ("report", "laporan", "brief")):
            return CapabilityType.REPORT
        if candidate_count > 3:
            return CapabilityType.COMPOSITE
        return CapabilityType.SKILL

    @staticmethod
    def _risk(statement: str, capabilities: Sequence[str]) -> RiskLevel:
        if any(word in statement for word in ("payment", "pembayaran", "release", "approve")):
            return "HIGH"
        if any(not key.endswith((".read", ".list", ".search")) for key in capabilities):
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _tokens(value: str) -> tuple[str, ...]:
        return tuple(token for token in re.findall(r"[a-z0-9_]+", value) if len(token) > 2)
