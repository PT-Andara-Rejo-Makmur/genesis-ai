import hashlib

import pytest
from pydantic import ValidationError

from genesis.model_gateway import GovernedModelGateway, ModelRequest, ModelResponse
from genesis.model_gateway.budget import ExecutionBudgetGuard
from genesis.model_gateway.policy import ModelAccessDenied, StaticModelPolicy
from genesis.model_gateway.routing import StaticModelRouter
from genesis.research.engine import (
    DocumentAnalysisRequest,
    DocumentIntelligence,
    DocumentSource,
    SemanticAnswerInvalid,
    validate_semantic_answer,
)


class SourceBoundProvider:
    async def complete(self, request: ModelRequest, *, route_id: str) -> ModelResponse:
        assert request.prompt_id == "genesis.document-semantic-analysis"
        assert "L1: Kebijakan aktif." in request.messages[0]["content"]
        return ModelResponse(
            content=(
                "Jawaban Ringkas\nKebijakan aktif [Sumber L1-L1]\n"
                "Temuan dan Kekurangan\nTidak ada.\nChecklist Perbaikan\nTinjau berkala.\n"
                "Batasan dan Informasi yang Belum Tersedia\nHanya satu baris.\n"
                "Sumber\n[Sumber L1-L1]"
            ),
            route_id=route_id,
            input_tokens=20,
            output_tokens=30,
        )


def source(*, classification: str = "INTERNAL") -> DocumentSource:
    content = "Kebijakan aktif."
    return DocumentSource(
        source_id="source_policy_001",
        title="Kebijakan",
        version="1.0.0",
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        status="APPROVED",
        data_classification=classification,
        content=content,
    )


@pytest.mark.asyncio
async def test_document_intelligence_is_source_bound_and_uses_model_gateway() -> None:
    gateway = GovernedModelGateway(
        policy=StaticModelPolicy(frozenset({"policy.document"})),
        budget_guard=ExecutionBudgetGuard(),
        router=StaticModelRouter(
            routes={"route.test": SourceBoundProvider()},
            policy_routes={"policy.document": "route.test"},
        ),
    )
    result = await DocumentIntelligence(gateway).analyze(
        DocumentAnalysisRequest(
            run_id="run_document_001",
            correlation_id="corr_document_001",
            question="Apa status kebijakan?",
            source=source(),
            policy_ref="policy.document",
        )
    )

    assert result.source_id == "source_policy_001"
    assert result.output_state == "AI_INFERRED"
    assert result.prompt_version == "1.0.0"


def test_document_source_rejects_digest_mismatch() -> None:
    with pytest.raises(ValidationError, match="content_sha256"):
        DocumentSource(
            source_id="source_policy_001",
            title="Kebijakan",
            version="1.0.0",
            content_sha256="0" * 64,
            status="APPROVED",
            content="content differs",
        )


def test_semantic_answer_rejects_out_of_bounds_citation() -> None:
    answer = "\n".join(
        (
            "Jawaban Ringkas [Sumber L1-L8]",
            "Temuan dan Kekurangan",
            "Checklist Perbaikan",
            "Batasan dan Informasi yang Belum Tersedia",
            "Sumber",
        )
    )
    with pytest.raises(SemanticAnswerInvalid, match="outside source bounds"):
        validate_semantic_answer(answer, source_line_count=1)


@pytest.mark.asyncio
async def test_model_policy_blocks_classification_before_provider() -> None:
    gateway = GovernedModelGateway(
        policy=StaticModelPolicy(
            frozenset({"policy.document"}), maximum_data_classification="INTERNAL"
        ),
        budget_guard=ExecutionBudgetGuard(),
        router=StaticModelRouter(
            routes={"route.test": SourceBoundProvider()},
            policy_routes={"policy.document": "route.test"},
        ),
    )
    with pytest.raises(ModelAccessDenied, match="CONFIDENTIAL"):
        await DocumentIntelligence(gateway).analyze(
            DocumentAnalysisRequest(
                run_id="run_document_002",
                correlation_id="corr_document_002",
                question="Apa status kebijakan?",
                source=source(classification="CONFIDENTIAL"),  # type: ignore[arg-type]
                policy_ref="policy.document",
            )
        )
