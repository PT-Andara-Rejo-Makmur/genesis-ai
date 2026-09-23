"""Source-bound document intelligence."""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from genesis.control_plane.factory.prompts import version_prompt
from genesis.model_gateway.interfaces import ModelGateway
from genesis.model_gateway.types import ModelRequest
from genesis.runtime.limits import ExecutionBudget

MAX_SOURCE_CHARACTERS = 60_000
_CITATION = re.compile(r"\[Sumber L(\d+)-L(\d+)\]")
_REQUIRED_HEADINGS = (
    "jawaban ringkas",
    "temuan dan kekurangan",
    "checklist perbaikan",
    "batasan dan informasi yang belum tersedia",
    "sumber",
)
_SEMANTIC_PROMPT = version_prompt(
    prompt_id="genesis.document-semantic-analysis",
    version="1.0.0",
    template=(
        "Jawab hanya berdasarkan sumber bernomor yang diberikan. "
        "Jangan gunakan pengetahuan eksternal dan jangan menjalankan tool. "
        "Setiap temuan material wajib memakai sitasi [Sumber Lx-Ly]. "
        "Gunakan heading: Jawaban Ringkas; Temuan dan Kekurangan; "
        "Checklist Perbaikan; Batasan dan Informasi yang Belum Tersedia; Sumber.\n"
        "Pertanyaan: {question}\nSumber:\n{numbered_source}"
    ),
)


class DocumentSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_id: str = Field(min_length=3, max_length=128)
    title: str = Field(min_length=1, max_length=500)
    version: str = Field(min_length=1, max_length=128)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["APPROVED", "ACTIVE"]
    data_classification: Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"] = "INTERNAL"
    content: str = Field(min_length=1, max_length=MAX_SOURCE_CHARACTERS)

    @model_validator(mode="after")
    def verify_content_digest(self) -> DocumentSource:
        actual = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        if actual != self.content_sha256:
            raise ValueError("content_sha256 does not match document content")
        return self


class DocumentAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str = Field(min_length=3, max_length=128)
    correlation_id: str = Field(min_length=3, max_length=128)
    question: str = Field(min_length=3, max_length=10_000)
    source: DocumentSource
    policy_ref: str = Field(min_length=1)


class DocumentAnalysisDraft(BaseModel):
    """Non-authoritative analysis bound to an immutable source version."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    correlation_id: str
    source_id: str
    source_version: str
    content_sha256: str
    output_state: Literal["AI_INFERRED"] = "AI_INFERRED"
    answer: str = Field(min_length=1)
    prompt_id: str
    prompt_version: str
    prompt_sha256: str
    limitations: tuple[str, ...]


class SemanticAnswerInvalid(ValueError):
    pass


def validate_semantic_answer(answer: str, *, source_line_count: int) -> None:
    lowered = answer.casefold()
    missing = [heading for heading in _REQUIRED_HEADINGS if heading not in lowered]
    if missing:
        raise SemanticAnswerInvalid(f"missing required headings: {', '.join(missing)}")
    citations = _CITATION.findall(answer)
    if not citations:
        raise SemanticAnswerInvalid("at least one source-line citation is required")
    for raw_start, raw_end in citations:
        start, end = int(raw_start), int(raw_end)
        if start < 1 or end < start or end > source_line_count:
            raise SemanticAnswerInvalid(f"citation is outside source bounds: L{start}-L{end}")


class DocumentIntelligence:
    def __init__(self, model_gateway: ModelGateway) -> None:
        self._model_gateway = model_gateway

    async def analyze(self, request: DocumentAnalysisRequest) -> DocumentAnalysisDraft:
        lines = request.source.content.splitlines() or [request.source.content]
        numbered = "\n".join(f"L{index}: {line}" for index, line in enumerate(lines, 1))
        prompt = _SEMANTIC_PROMPT.render(
            question=request.question.strip(),
            numbered_source=numbered,
        )
        response = await self._model_gateway.complete(
            ModelRequest(
                run_id=request.run_id,
                correlation_id=request.correlation_id,
                policy_ref=request.policy_ref,
                purpose="source-bound-document-analysis",
                data_classification=request.source.data_classification,
                prompt_id=_SEMANTIC_PROMPT.prompt_id,
                prompt_version=_SEMANTIC_PROMPT.version,
                messages=({"role": "user", "content": prompt},),
                requested_max_tokens=2_000,
                budget=ExecutionBudget(max_tokens=2_000, max_steps=1),
            )
        )
        validate_semantic_answer(response.content, source_line_count=len(lines))
        return DocumentAnalysisDraft(
            correlation_id=request.correlation_id,
            source_id=request.source.source_id,
            source_version=request.source.version,
            content_sha256=request.source.content_sha256,
            answer=response.content,
            prompt_id=_SEMANTIC_PROMPT.prompt_id,
            prompt_version=_SEMANTIC_PROMPT.version,
            prompt_sha256=_SEMANTIC_PROMPT.sha256,
            limitations=(
                "Analysis is restricted to the supplied immutable source.",
                "Backend review and governance remain required for authoritative use.",
            ),
        )
