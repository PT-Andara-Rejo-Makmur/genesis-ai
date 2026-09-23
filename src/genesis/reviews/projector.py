"""Explicit projection of internal review findings to Contracts 1.5.0."""

from collections.abc import Mapping
from typing import Any

from genesis.contracts import CanonicalContractCatalog

AI_REVIEW_SCHEMA = "https://schemas.alos.dev/v1/review/ai-review-result.schema.json"


class CanonicalAIReviewProjector:
    def __init__(self, contracts: CanonicalContractCatalog) -> None:
        self._contracts = contracts

    def project(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._contracts.validate(AI_REVIEW_SCHEMA, payload)
