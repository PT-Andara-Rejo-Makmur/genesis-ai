from genesis.model_gateway.types import ModelRequest


class ModelAccessDenied(Exception):
    pass


class StaticModelPolicy:
    def __init__(self, allowed_policy_refs: frozenset[str]) -> None:
        self._allowed = allowed_policy_refs

    def authorize(self, request: ModelRequest) -> None:
        if request.policy_ref not in self._allowed:
            raise ModelAccessDenied(f"Model policy is not allowed: {request.policy_ref}")
