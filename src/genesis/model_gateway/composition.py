"""One governed production boundary, with explicit disabled configuration."""

import httpx

from genesis.adapters.providers.disabled import DisabledProviderAdapter
from genesis.adapters.providers.nine_router import NineRouterProviderAdapter
from genesis.config import Settings
from genesis.model_gateway.budget.guard import ExecutionBudgetGuard
from genesis.model_gateway.interfaces import ModelProviderAdapter
from genesis.model_gateway.policy.static import StaticModelPolicy
from genesis.model_gateway.routing.static import StaticModelRouter
from genesis.model_gateway.service import GovernedModelGateway
from genesis.model_gateway.types import ProviderReadiness

PRODUCTION_POLICIES = frozenset(
    {
        "ara.production",
        "policy.fast",
        "policy.standard",
        "policy.reasoning",
        "policy.coding",
        "policy.critical",
        "policy.evidence-bound-research.v1",
    }
)


async def provider_readiness(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
    policy_ref: str = "ara.production",
) -> ProviderReadiness:
    return await NineRouterProviderAdapter(settings, client=client).readiness(policy_ref=policy_ref)


def build_provider_adapter(
    settings: Settings, *, client: httpx.AsyncClient | None = None
) -> ModelProviderAdapter:
    if not settings.production_runtime_enabled:
        return DisabledProviderAdapter()
    return NineRouterProviderAdapter(settings, client=client)


def build_model_gateway(
    settings: Settings, *, client: httpx.AsyncClient | None = None
) -> GovernedModelGateway:
    return GovernedModelGateway(
        policy=StaticModelPolicy(
            PRODUCTION_POLICIES,
            maximum_data_classification=settings.NINE_ROUTER_MAXIMUM_CLASSIFICATION,
        ),
        budget_guard=ExecutionBudgetGuard(),
        router=StaticModelRouter(
            {"nine_router": build_provider_adapter(settings, client=client)},
            {policy: "nine_router" for policy in PRODUCTION_POLICIES},
        ),
    )
