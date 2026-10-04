"""Optional manual smoke. Requires operator-supplied runtime credentials; never normal CI."""

import asyncio
import json

from genesis.adapters.providers.nine_router import NineRouterProviderAdapter, ProviderFailure
from genesis.config import Settings
from genesis.model_gateway.composition import build_model_gateway
from genesis.model_gateway.budget.guard import BudgetExceeded
from genesis.model_gateway.types import ModelRequest
from genesis.runtime.limits import ExecutionBudget


async def main() -> int:
    settings = Settings()
    if not settings.NINE_ROUTER_API_KEY.get_secret_value():
        print("CREDENTIAL_PENDING: NINE_ROUTER_API_KEY is not configured.")
        return 0
    adapter = NineRouterProviderAdapter(settings)
    readiness = await adapter.readiness(policy_ref="policy.standard")
    print(readiness.model_dump_json())
    if readiness.status != "CONNECTED":
        return 1
    try:
        result = await build_model_gateway(settings).complete(
            ModelRequest(
                run_id="run_provider_smoke",
                correlation_id="corr_provider_smoke",
                policy_ref="policy.standard",
                purpose="manual provider connectivity",
                data_classification="PUBLIC",
                messages=({"role": "user", "content": "Reply only OK."},),
                requested_max_tokens=32,
                # Provider-reported usage includes prompt and reasoning tokens, not
                # just the requested visible reply. Keep a finite connectivity budget.
                budget=ExecutionBudget(max_tokens=4096, max_steps=1),
            )
        )
    except ProviderFailure as exc:
        print(json.dumps({"status": "FAILED", "code": exc.code}))
        return 1
    except BudgetExceeded as exc:
        response = exc.response
        print(json.dumps({"status": "FAILED", "code": "BUDGET_EXCEEDED",
                          "input_tokens": response.input_tokens if response else None,
                          "output_tokens": response.output_tokens if response else None}))
        return 1
    if result.content.strip() != "OK":
        print(json.dumps({"status": "FAILED", "code": "UNEXPECTED_SMOKE_REPLY"}))
        return 1
    print(
        json.dumps(
            {
                "status": "PASS",
                "route_id": result.route_id,
                "provider_request_id": result.provider_request_id,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "cost": result.cost,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
