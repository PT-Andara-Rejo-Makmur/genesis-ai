"""The only permitted model access boundary for GENESIS."""

from genesis.model_gateway.service import GovernedModelGateway
from genesis.model_gateway.types import ModelRequest, ModelResponse

__all__ = ["GovernedModelGateway", "ModelRequest", "ModelResponse"]
