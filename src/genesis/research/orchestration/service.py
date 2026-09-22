"""One generic H7 research intelligence pipeline across all R&D domains."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from genesis.contracts import CanonicalContractCatalog
from genesis.research.decision import (
    EvidenceCandidate,
    ExternalResearchBoundary,
    ExternalResearchDecider,
    ResearchChannel,
    ResearchDecisionRequest,
    ResearchRisk,
)
from genesis.research.models import ResearchDomain
from genesis.research.orchestration.builder import (
    CanonicalResearchProjector,
    FindingRecommendationBuilder,
)
from genesis.research.orchestration.claims import ResearchClaimExtractor
from genesis.research.orchestration.comparison import ClaimComparisonIntelligence
from genesis.research.orchestration.models import (
    ClaimAssessment,
    ClaimKind,
    DelegatedResearchInput,
    EvidenceUsability,
    ResearchEvidenceItem,
    ResearchOrchestrationFailure,
    ResearchOrchestrationResult,
    RetrievalAttempt,
    RetrievalStatus,
    SourceMode,
)
from genesis.research.orchestration.planner import (
    ResearchQuestionPlanner,
    execution_budget,
)
from genesis.research.orchestration.provider import (
    ResearchEvidenceProvider,
    ResearchRetrievalRequest,
)
from genesis.research.orchestration.quality import EvidenceQualityPolicy
from genesis.research.sources import FreshnessStatus, SourceReliability
from genesis.research.tool_selection import (
    AuthorizedResearchTool,
    ResearchToolCategory,
    ResearchToolSelectionKind,
    ResearchToolSelectionPolicy,
    ResearchToolSelectionRequest,
)
from genesis.runtime.context import DataClassification

RESEARCH_REQUEST_SCHEMA = "https://schemas.alos.dev/v1/research/research-request.schema.json"
_MAX_EVIDENCE_ITEMS = 12
_MAX_TOTAL_CHARACTERS = 12_000


class ResearchOrchestrator:
    """Research intelligence only; Backend owns retrieval authority and persistence."""

    def __init__(
        self,
        *,
        contracts: CanonicalContractCatalog,
        question_planner: ResearchQuestionPlanner,
        claim_extractor: ResearchClaimExtractor,
        evidence_provider: ResearchEvidenceProvider | None = None,
        quality_policy: EvidenceQualityPolicy | None = None,
        comparison: ClaimComparisonIntelligence | None = None,
        builder: FindingRecommendationBuilder | None = None,
    ) -> None:
        self._contracts = contracts
        self._question_planner = question_planner
        self._claim_extractor = claim_extractor
        self._provider = evidence_provider
        self._quality = quality_policy or EvidenceQualityPolicy()
        self._comparison = comparison or ClaimComparisonIntelligence()
        self._builder = builder or FindingRecommendationBuilder()
        self._tool_policy = ResearchToolSelectionPolicy(
            evidence_decider=ExternalResearchDecider(contracts=contracts)
        )
        self._projector = CanonicalResearchProjector(contracts=contracts)

    async def orchestrate(
        self,
        payload: Mapping[str, Any],
        *,
        existing_evidence: tuple[ResearchEvidenceItem, ...] = (),
        memory_evidence: tuple[ResearchEvidenceItem, ...] = (),
        delegated_inputs: tuple[DelegatedResearchInput, ...] = (),
        authorized_tools: tuple[AuthorizedResearchTool, ...] = (),
        risk: ResearchRisk = ResearchRisk.MEDIUM,
        maximum_external_cost: float = 0,
        maximum_tool_cost: float | None = None,
    ) -> ResearchOrchestrationResult:
        request = self._contracts.validate(RESEARCH_REQUEST_SCHEMA, payload)
        correlation_id = str(request["correlation_id"])
        if request.get("domain") is None:
            raise ResearchOrchestrationFailure(
                "RESEARCH_DOMAIN_REQUIRED",
                "H7 orchestration requires one explicit typed domain.",
                correlation_id,
            )
        domain = ResearchDomain(str(request["domain"]))
        context = request["execution_context"]
        assert isinstance(context, Mapping)
        budget = execution_budget(context)
        planned = await self._question_planner.plan(
            research_id=str(request["research_id"]),
            run_id=str(request["run_id"]),
            correlation_id=correlation_id,
            domain=domain,
            question=str(request["question"]),
            scope_refs=tuple(context["scope_refs"]),
            data_classification=str(context["data_classification"]),
            budget=budget,
        )
        evidence: list[ResearchEvidenceItem] = [*existing_evidence, *memory_evidence]
        limitations: list[str] = list(planned.plan.limitations)
        for child in delegated_inputs:
            if child.status == "COMPLETED" and child.validation_status == "VALID":
                evidence.extend(child.evidence_items)
            else:
                limitations.append(f"CHILD_{child.child_task_id}_{child.status}_NOT_PROMOTED")
        evidence = self._bounded_unique(evidence)
        attempts: list[RetrievalAttempt] = []
        for subquery in planned.plan.subqueries:
            relevant = tuple(
                item
                for item in evidence
                if not item.subquery_ids or subquery.subquery_id in item.subquery_ids
            )
            candidates = tuple(self._candidate(item, memory_evidence) for item in relevant)
            external_tool = next(
                (
                    item
                    for item in authorized_tools
                    if item.category is ResearchToolCategory.EXTERNAL_RESEARCH
                ),
                None,
            )
            decision_request = ResearchDecisionRequest(
                correlation_id=correlation_id,
                domain=domain,
                question=subquery.question,
                risk=risk,
                data_classification=DataClassification(str(context["data_classification"])),
                authorized_scope_refs=tuple(context["scope_refs"]),
                authorized_permission_refs=tuple(context.get("permission_refs", [])),
                allowed_tool_ids=tuple(context.get("allowed_tool_ids", [])),
                evidence=candidates,
                external=ExternalResearchBoundary(
                    enabled=external_tool is not None,
                    tool_id=(
                        external_tool.tool_id
                        if external_tool is not None
                        else "research.external.retrieve"
                    ),
                    permission_ref=(
                        external_tool.permission_refs[0]
                        if external_tool is not None and external_tool.permission_refs
                        else "research.external.read"
                    ),
                    estimated_cost=(
                        external_tool.estimated_cost if external_tool is not None else 0
                    ),
                ),
                maximum_external_cost=maximum_external_cost,
            )
            selection = self._tool_policy.select(
                ResearchToolSelectionRequest(
                    evidence_request=decision_request,
                    available_tools=authorized_tools,
                    maximum_tool_cost=maximum_tool_cost,
                )
            )
            if selection.kind is ResearchToolSelectionKind.USE_EXISTING_EVIDENCE:
                attempts.append(
                    RetrievalAttempt(
                        subquery_id=subquery.subquery_id,
                        status=RetrievalStatus.SUCCESS,
                        evidence_ids=selection.selected_evidence_ids,
                        reason_codes=selection.reason_codes,
                    )
                )
                continue
            if selection.kind is not ResearchToolSelectionKind.SELECT_TOOL:
                code = selection.reason_codes[0]
                attempts.append(
                    RetrievalAttempt(
                        subquery_id=subquery.subquery_id,
                        status=RetrievalStatus.NO_RESULT,
                        reason_codes=selection.reason_codes,
                    )
                )
                limitations.append(f"{subquery.subquery_id}:{code}")
                continue
            if self._provider is None:
                attempts.append(
                    RetrievalAttempt(
                        subquery_id=subquery.subquery_id,
                        tool_id=selection.selected_tool_id,
                        category=selection.selected_category,
                        status=RetrievalStatus.DENIED,
                        reason_codes=("RESEARCH_PROVIDER_UNAVAILABLE",),
                    )
                )
                limitations.append(f"{subquery.subquery_id}:RESEARCH_PROVIDER_UNAVAILABLE")
                continue
            try:
                retrieved = await self._provider.retrieve(
                    ResearchRetrievalRequest(
                        run_id=str(request["run_id"]),
                        correlation_id=correlation_id,
                        subquery=subquery,
                        selected_tool_id=str(selection.selected_tool_id),
                        selected_category=selection.selected_category,
                        execution_context=dict(context),
                        source_constraints=tuple(request.get("constraints", [])),
                    )
                )
            except Exception:
                retrieved = None
            if retrieved is None:
                status = RetrievalStatus.FAILED
                reason_codes = ("RESEARCH_PROVIDER_FAILED",)
                retrieved_items: tuple[ResearchEvidenceItem, ...] = ()
            else:
                status = retrieved.status
                reason_codes = (
                    (retrieved.error_code,) if retrieved.error_code else (retrieved.status.value,)
                )
                retrieved_items = retrieved.items if status is RetrievalStatus.SUCCESS else ()
                limitations.extend(retrieved.limitations)
            attempts.append(
                RetrievalAttempt(
                    subquery_id=subquery.subquery_id,
                    tool_id=selection.selected_tool_id,
                    category=selection.selected_category,
                    status=status,
                    evidence_ids=tuple(item.evidence_id for item in retrieved_items),
                    reason_codes=reason_codes,
                )
            )
            if status is not RetrievalStatus.SUCCESS:
                limitations.append(f"{subquery.subquery_id}:RETRIEVAL_{status.value}")
            evidence = self._bounded_unique([*evidence, *retrieved_items])

        assessments = tuple(self._quality.assess(item, context) for item in evidence)
        usable = tuple(
            item
            for item in evidence
            if next(
                assessment
                for assessment in assessments
                if assessment.evidence_id == item.evidence_id
            ).usability
            is not EvidenceUsability.EXCLUDED
        )
        if usable:
            extracted = await self._claim_extractor.extract(
                plan=planned.plan,
                evidence_items=usable,
                assessments=assessments,
                run_id=str(request["run_id"]),
                correlation_id=correlation_id,
                data_classification=str(context["data_classification"]),
                budget=budget,
                prior_usage=planned.usage,
            )
            claims = extracted.claims
            usage = planned.usage.add(extracted.usage)
        else:
            claims = tuple(
                ClaimAssessment(
                    claim_id=f"gap_{item.subquery_id}",
                    normalized_topic=item.subquery_id,
                    statement=f"Evidence is insufficient for: {item.question}",
                    kind=ClaimKind.GAP,
                    evidence_ids=(),
                    source_ids=(),
                    source_versions=(),
                    confidence=0.1,
                    limitations=("EVIDENCE_GAP",),
                )
                for item in planned.plan.subqueries
            )
            usage = planned.usage
            limitations.append("INSUFFICIENT_USABLE_EVIDENCE")
        duplicates, corroborations, conflicts = self._comparison.compare(claims, assessments)
        findings, recommendations = self._builder.build(
            domain=domain,
            claims=claims,
            conflicts=conflicts,
            corroborations=corroborations,
            assessments=assessments,
        )
        limitations.extend(
            limitation for conflict in conflicts for limitation in conflict.limitations
        )
        canonical = self._projector.project(
            request=request,
            findings=findings,
            recommendations=recommendations,
            evidence_items=usable,
            limitations=tuple(dict.fromkeys(limitations)),
        )
        return ResearchOrchestrationResult(
            plan=planned.plan,
            source_mode=self._source_mode(usable),
            retrieval_attempts=tuple(attempts),
            evidence_items=usable,
            evidence_assessments=assessments,
            claims=claims,
            duplicates=duplicates,
            corroborations=corroborations,
            conflicts=conflicts,
            assumptions=tuple(item for item in claims if item.kind is ClaimKind.ASSUMPTION),
            gaps=tuple(item for item in claims if item.kind is ClaimKind.GAP),
            findings=findings,
            recommendations=recommendations,
            canonical_result=canonical,
            limitations=tuple(dict.fromkeys(limitations)),
            usage=usage,
        )

    @staticmethod
    def _candidate(
        item: ResearchEvidenceItem,
        memory_evidence: tuple[ResearchEvidenceItem, ...],
    ) -> EvidenceCandidate:
        ref = item.evidence_ref
        return EvidenceCandidate(
            evidence_id=item.evidence_id,
            channel=(
                ResearchChannel.MEMORY
                if item in memory_evidence
                or item.category is ResearchToolCategory.MEMORY
                else ResearchChannel.INTERNAL_SOURCE
            ),
            freshness=FreshnessStatus(str(ref.get("freshness", "UNKNOWN"))),
            reliability=SourceReliability(str(ref.get("reliability", "UNVERIFIED"))),
            available=ref.get("validation_status") == "VALID",
            scope_refs=tuple(ref.get("scope_refs", [])),
            data_classification=DataClassification(
                str(ref.get("data_classification", "RESTRICTED"))
            ),
        )

    @staticmethod
    def _bounded_unique(
        items: list[ResearchEvidenceItem],
    ) -> list[ResearchEvidenceItem]:
        result: list[ResearchEvidenceItem] = []
        seen: set[str] = set()
        characters = 0
        for item in items:
            if item.evidence_id in seen or len(result) >= _MAX_EVIDENCE_ITEMS:
                continue
            if characters + len(item.content) > _MAX_TOTAL_CHARACTERS:
                continue
            seen.add(item.evidence_id)
            characters += len(item.content)
            result.append(item)
        return result

    @staticmethod
    def _source_mode(items: tuple[ResearchEvidenceItem, ...]) -> SourceMode:
        external = any(item.evidence_ref.get("source_type") == "EXTERNAL" for item in items)
        internal = any(item.evidence_ref.get("source_type") != "EXTERNAL" for item in items)
        if external and internal:
            return SourceMode.MIXED
        if external:
            return SourceMode.EXTERNAL_ONLY
        if internal:
            return SourceMode.INTERNAL_ONLY
        return SourceMode.NONE


def evidence_items_from_context(
    context_bundle: Mapping[str, Any],
) -> tuple[ResearchEvidenceItem, ...]:
    """Project already-authorized ContextBundle evidence into bounded H7 data."""

    content_by_evidence = {
        str(item.get("evidence_id")): str(item.get("value", ""))
        for item in context_bundle.get("items", [])
        if isinstance(item, Mapping) and item.get("evidence_id")
    }
    result: list[ResearchEvidenceItem] = []
    for ref in context_bundle.get("evidence_refs", []):
        if not isinstance(ref, Mapping):
            continue
        evidence_id = str(ref.get("evidence_id", ""))
        content = content_by_evidence.get(evidence_id) or str(ref.get("excerpt", ""))
        if not content:
            continue
        source_type = str(ref.get("source_type", "INTERNAL"))
        result.append(
            ResearchEvidenceItem(
                evidence_ref=dict(ref),
                content=content[:4_000],
                category=(
                    ResearchToolCategory.EXTERNAL_RESEARCH
                    if source_type == "EXTERNAL"
                    else ResearchToolCategory.INTERNAL_DOCUMENT
                ),
            )
        )
    return tuple(result)
