from typing import ClassVar

from genesis.model_gateway.types import ModelRequest


class ModelAccessDenied(Exception):
    pass


class StaticModelPolicy:
    _CLASSIFICATION_RANK: ClassVar[dict[str, int]] = {
        "PUBLIC": 0,
        "INTERNAL": 1,
        "CONFIDENTIAL": 2,
        "RESTRICTED": 3,
    }

    def __init__(
        self,
        allowed_policy_refs: frozenset[str],
        *,
        maximum_data_classification: str = "INTERNAL",
    ) -> None:
        self._allowed = allowed_policy_refs
        if maximum_data_classification not in self._CLASSIFICATION_RANK:
            raise ValueError("Unknown maximum data classification")
        self._maximum_data_classification = maximum_data_classification

    def authorize(self, request: ModelRequest) -> None:
        if request.policy_ref not in self._allowed:
            raise ModelAccessDenied(f"Model policy is not allowed: {request.policy_ref}")
        if (
            self._CLASSIFICATION_RANK[request.data_classification]
            > self._CLASSIFICATION_RANK[self._maximum_data_classification]
        ):
            raise ModelAccessDenied(
                f"Model policy does not allow data classification: {request.data_classification}"
            )
