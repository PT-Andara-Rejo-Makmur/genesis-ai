"""Evidence-bound research reasoning; outputs remain non-authoritative."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from genesis.contracts import CanonicalContractCatalog
from genesis.control_plane.factory.prompts import version_prompt
from genesis.model_gateway.interfaces import ModelGateway
from genesis.model_gateway.types import ModelRequest
from genesis.runtime.assistant.sources import data_only, display
from genesis.runtime.limits import ExecutionBudget

if TYPE_CHECKING:
    from genesis.research.orchestration import ResearchOrchestrator

RESEARCH_REQUEST_SCHEMA = "https://schemas.alos.dev/v1/research/research-request.schema.json"
RESEARCH_RESULT_SCHEMA = "https://schemas.alos.dev/v1/research/research-result.schema.json"
CONTEXT_BUNDLE_SCHEMA = "https://schemas.alos.dev/v1/context/context-bundle.schema.json"

_RESEARCH_PROMPT = version_prompt(
    prompt_id="genesis.research.evidence-bound",
    version="1.0.0",
    template=(
        "Analyze only the supplied ContextBundle. Return JSON with findings, recommendations, "
        "and limitations. Every finding must cite one or more evidence_ids from the bundle. "
        "Recommendations are backlog candidates only and never approvals or executable commands. "
        "Question: {question}\nContextBundle: {context_bundle}"
    ),
)


class _FindingDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finding_id: str = Field(min_length=3)
    finding_type: str = "RESEARCH"
    domain: str | None = None
    title: str | None = None
    statement: str = Field(min_length=1)
    severity: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)


class _RecommendationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommendation_id: str = Field(min_length=3)
    summary: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    finding_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    backlog_candidate: bool = True


class _ResearchDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: list[_FindingDraft]
    recommendations: list[_RecommendationDraft]
    limitations: list[str] = Field(default_factory=list)


class ContextProvider(Protocol):
    async def retrieve(
        self,
        *,
        run_id: str,
        query: str,
        execution_context: Mapping[str, Any],
        limit: int = 12,
        max_characters: int = 12_000,
    ) -> dict[str, Any]: ...


class ResearchOutputInvalid(ValueError):
    pass


class ResearchEngine:
    """Canonical ResearchRequest-to-ResearchResult application facade."""

    def __init__(
        self,
        *,
        contracts: CanonicalContractCatalog,
        model_gateway: ModelGateway,
        context_provider: ContextProvider | None = None,
        orchestrator: ResearchOrchestrator | None = None,
        production: bool = False,
    ) -> None:
        self._contracts = contracts
        self._model_gateway = model_gateway
        self._context_provider = context_provider
        self._orchestrator = orchestrator
        self._production = production

    async def research(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        request = self._contracts.validate(RESEARCH_REQUEST_SCHEMA, payload)
        execution_context = request["execution_context"]
        assert isinstance(execution_context, Mapping)
        context = request.get("context_bundle")
        if context is None:
            if self._context_provider is None:
                raise ResearchOutputInvalid(
                    "ResearchRequest requires context_bundle or a Backend context provider"
                )
            context = await self._context_provider.retrieve(
                run_id=str(request["run_id"]),
                query=str(request["question"]),
                execution_context=execution_context,
            )
        if not isinstance(context, Mapping):
            raise ResearchOutputInvalid("context_bundle must be an object")
        validated_context = self._contracts.validate(CONTEXT_BUNDLE_SCHEMA, context)
        self._validate_context_identity(validated_context, execution_context)
        if self._orchestrator is not None:
            from genesis.research.orchestration import evidence_items_from_context

            analysis = await self._orchestrator.orchestrate(
                request,
                existing_evidence=evidence_items_from_context(validated_context),
            )
            return analysis.canonical_result
        evidence_by_id = {
            str(ref["evidence_id"]): ref for ref in validated_context.get("evidence_refs", [])
        }
        if not evidence_by_id:
            raise ResearchOutputInvalid(
                "Research requires at least one canonical evidence reference"
            )
        if self._production:
            from genesis.runtime.agentic.state import known_evidence

            admitted = known_evidence(
                {"execution_context": dict(execution_context), "context_bundle": validated_context}
            )
            if set(admitted) != set(evidence_by_id) or any(
                ref.get("run_id") != request["run_id"]
                or ref.get("correlation_id") != request["correlation_id"]
                for ref in admitted.values()
            ):
                raise ResearchOutputInvalid(
                    "Production research requires current admitted evidence with exact run lineage"
                )

        budget_payload = execution_context.get("execution_budget")
        max_tokens = 2_000
        if isinstance(budget_payload, Mapping) and isinstance(
            budget_payload.get("max_tokens"), int
        ):
            max_tokens = min(max_tokens, int(budget_payload["max_tokens"]))
        prompt = _RESEARCH_PROMPT.render(
            question=str(request["question"]),
            context_bundle=json.dumps(
                {
                    "items": [
                        {
                            key: data_only(item[key])
                            for key in (
                                "key",
                                "value",
                                "source_id",
                                "evidence_id",
                                "content_hash",
                                "instruction_authority",
                            )
                            if key in item
                        }
                        for item in validated_context.get("items", [])
                    ],
                    "evidence_refs": [
                        {
                            key: ref.get(key)
                            for key in (
                                "evidence_id",
                                "source_id",
                                "content_hash",
                                "freshness",
                                "instruction_authority",
                            )
                        }
                        for ref in evidence_by_id.values()
                    ],
                }
                if self._production
                else validated_context,
                sort_keys=True,
            ),
        )
        response = await self._model_gateway.complete(
            ModelRequest(
                run_id=str(request["run_id"]),
                correlation_id=str(request["correlation_id"]),
                policy_ref="policy.evidence-bound-research.v1",
                purpose="evidence-bound-research",
                data_classification=execution_context["data_classification"],
                prompt_id=_RESEARCH_PROMPT.prompt_id,
                prompt_version=_RESEARCH_PROMPT.version,
                messages=({"role": "user", "content": prompt},),
                requested_max_tokens=max_tokens,
                budget=ExecutionBudget.model_validate(dict(budget_payload))
                if isinstance(budget_payload, Mapping)
                else ExecutionBudget(max_tokens=max_tokens, max_steps=1),
            )
        )
        try:
            draft = _ResearchDraft.model_validate_json(response.content)
        except ValidationError as exc:
            raise ResearchOutputInvalid("ModelGateway returned an invalid research draft") from exc
        identifiers = {item.finding_id for item in draft.findings}
        if len(identifiers) != len(draft.findings) or any(
            not item.finding_ids or not set(item.finding_ids).issubset(identifiers)
            for item in draft.recommendations
        ):
            raise ResearchOutputInvalid("Recommendations require exact finding references")
        if self._production:
            bound_ids = {
                item: self._identifier("finding", str(request["run_id"]) + ":" + item)
                for item in identifiers
            }
            for finding in draft.findings:
                values = [
                    item.get("value")
                    for item in validated_context.get("items", [])
                    if item.get("evidence_id") in finding.evidence_ids
                    and item.get("instruction_authority") is False
                ]
                if not values:
                    raise ResearchOutputInvalid(
                        "Factual research findings require current canonical source values"
                    )
                finding.finding_id = bound_ids[finding.finding_id]
                # Free prose from the provider remains advisory; factual findings are canonical.
                finding.statement = "\n\n".join(display(data_only(value)) for value in values)[
                    :18000
                ]
                finding.domain = str(request.get("domain", "TECHNOLOGY"))
            for recommendation in draft.recommendations:
                recommendation.finding_ids = [
                    bound_ids[item] for item in recommendation.finding_ids
                ]
                recommendation.recommendation_id = self._identifier(
                    "recommendation",
                    str(request["run_id"]) + ":" + recommendation.recommendation_id,
                )
        findings = [
            self._finding(
                item.model_copy(
                    update={"domain": item.domain or str(request.get("domain", "TECHNOLOGY"))}
                ),
                evidence_by_id,
            )
            for item in draft.findings
        ]
        recommendations = [
            self._recommendation(item, evidence_by_id) for item in draft.recommendations
        ]
        evidence_refs = list(evidence_by_id.values())
        result = {
            "research_id": request["research_id"],
            "run_id": request["run_id"],
            "tenant_id": execution_context["tenant_id"],
            "organization_id": execution_context["organization_id"],
            "workspace_id": execution_context["workspace_id"],
            "correlation_id": request["correlation_id"],
            "output_state": "NEEDS_REVIEW",
            "findings": findings,
            "recommendations": recommendations,
            "evidence_bundle": {
                "bundle_id": self._identifier(
                    "bundle", f"{request['research_id']}:{request['correlation_id']}"
                ),
                "tenant_id": execution_context["tenant_id"],
                "organization_id": execution_context["organization_id"],
                "workspace_id": execution_context["workspace_id"],
                "run_id": request["run_id"],
                "correlation_id": request["correlation_id"],
                "evidence_refs": evidence_refs,
            },
            "limitations": draft.limitations,
            "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        return self._contracts.validate(RESEARCH_RESULT_SCHEMA, result)

    @staticmethod
    def _validate_context_identity(
        context: Mapping[str, Any], execution_context: Mapping[str, Any]
    ) -> None:
        for field in (
            "tenant_id",
            "organization_id",
            "workspace_id",
            "actor_id",
            "correlation_id",
        ):
            if context[field] != execution_context[field]:
                raise ResearchOutputInvalid(
                    f"ContextBundle {field} does not match execution context"
                )

    @staticmethod
    def _references(evidence_ids: list[str], evidence_by_id: Mapping[str, Any]) -> list[Any]:
        unknown = [evidence_id for evidence_id in evidence_ids if evidence_id not in evidence_by_id]
        if unknown:
            raise ResearchOutputInvalid(
                f"Research draft cites unknown evidence: {', '.join(sorted(unknown))}"
            )
        return [evidence_by_id[evidence_id] for evidence_id in evidence_ids]

    def _finding(self, item: _FindingDraft, evidence_by_id: Mapping[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "finding_id": item.finding_id,
            "finding_type": item.finding_type,
            "statement": item.statement,
            "confidence": item.confidence,
            "output_state": "AI_INFERRED",
            "evidence_refs": self._references(item.evidence_ids, evidence_by_id),
            "limitations": item.limitations,
        }
        for key in ("domain", "title", "severity"):
            value = getattr(item, key)
            if value is not None:
                result[key] = value
        return result

    def _recommendation(
        self, item: _RecommendationDraft, evidence_by_id: Mapping[str, Any]
    ) -> dict[str, Any]:
        return {
            "recommendation_id": item.recommendation_id,
            "summary": item.summary,
            "recommended_action": item.recommended_action,
            "confidence": item.confidence,
            "author_type": "AI",
            "finding_ids": item.finding_ids,
            "evidence_refs": self._references(item.evidence_ids, evidence_by_id),
            "limitations": item.limitations,
            "backlog_candidate": item.backlog_candidate,
        }

    @staticmethod
    def _identifier(prefix: str, seed: str) -> str:
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
        return f"{prefix}_{digest}"
