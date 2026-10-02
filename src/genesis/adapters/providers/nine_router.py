"""Credential-safe, non-streaming transport to an external OpenAI-compatible router."""

from __future__ import annotations

import asyncio
import logging
import math
from time import monotonic
from typing import Any

import httpx

from genesis.config import Settings
from genesis.model_gateway.errors import ProviderFailure as ProviderFailure
from genesis.model_gateway.types import ModelRequest, ModelResponse, ProviderReadiness

logger = logging.getLogger(__name__)
_RETRY_STATUSES = {429, 502, 503, 504}
_POLICY_MODELS = {
    "policy.fast": "NINE_ROUTER_MODEL_FAST",
    "policy.standard": "NINE_ROUTER_MODEL_STANDARD",
    "ara.production": "NINE_ROUTER_MODEL_STANDARD",
    "policy.reasoning": "NINE_ROUTER_MODEL_REASONING",
    "policy.evidence-bound-research.v1": "NINE_ROUTER_MODEL_REASONING",
    "policy.coding": "NINE_ROUTER_MODEL_CODING",
    "policy.critical": "NINE_ROUTER_MODEL_CRITICAL",
}


class NineRouterProviderAdapter:
    """Transport only. Policy, authority, evidence, and business decisions remain upstream."""

    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client

    def _configured(self) -> bool:
        return bool(
            self._settings.production_runtime_enabled
            and self._settings.NINE_ROUTER_BASE_URL
            and self._settings.NINE_ROUTER_API_KEY.get_secret_value().strip()
        )

    async def _request(
        self, method: str, path: str, *, body: dict[str, Any] | None = None
    ) -> httpx.Response:
        if not self._configured():
            raise ProviderFailure("PROVIDER_CONFIGURATION_MISSING")
        # No redirects, ambient proxy credentials, response body errors, or request/header logging.
        client = self._client or httpx.AsyncClient(trust_env=False, follow_redirects=False)
        response: httpx.Response | None = None
        failure: ProviderFailure | None = None
        try:
            for attempt in range(2):
                uncertain_transport = False
                try:
                    response = await client.request(
                        method,
                        self._settings.NINE_ROUTER_BASE_URL + path,
                        headers={
                            "Authorization": "Bearer "
                            + self._settings.NINE_ROUTER_API_KEY.get_secret_value()
                        },
                        json=body,
                        timeout=httpx.Timeout(self._settings.NINE_ROUTER_TIMEOUT_SECONDS),
                        follow_redirects=False,
                    )
                    status = response.status_code
                    if status == 200:
                        return response
                    code = (
                        "PROVIDER_AUTHENTICATION_FAILED"
                        if status in {401, 403}
                        else "PROVIDER_RATE_LIMITED"
                        if status == 429
                        else "PROVIDER_MODEL_UNAVAILABLE"
                        if status == 404
                        else "PROVIDER_INVALID_REQUEST"
                        if status in {400, 422}
                        else "PROVIDER_UNAVAILABLE"
                    )
                    failure = ProviderFailure(
                        code, retryable=status in _RETRY_STATUSES, usage_unknown=method == "POST"
                    )
                except (httpx.ConnectError, httpx.ConnectTimeout):
                    failure = ProviderFailure("PROVIDER_UNAVAILABLE", retryable=True)
                except httpx.TimeoutException:
                    uncertain_transport = True
                    failure = ProviderFailure(
                        "PROVIDER_TIMEOUT", retryable=True, usage_unknown=method == "POST"
                    )
                except httpx.TransportError:
                    uncertain_transport = True
                    failure = ProviderFailure(
                        "PROVIDER_UNAVAILABLE", retryable=True, usage_unknown=method == "POST"
                    )
                if failure is None or not failure.retryable or attempt == 1:
                    break
                # Read timeout may mean inference already ran. Never repeat a possibly billed POST.
                if method == "POST" and uncertain_transport:
                    break
                await asyncio.sleep(0.1)
        finally:
            if self._client is None:
                await client.aclose()
        raise failure or ProviderFailure("PROVIDER_UNAVAILABLE")

    def _document(self, response: httpx.Response) -> dict[str, Any]:
        try:
            result = response.json()
        except ValueError:
            raise ProviderFailure("PROVIDER_INVALID_RESPONSE", usage_unknown=True) from None
        if not isinstance(result, dict):
            raise ProviderFailure("PROVIDER_INVALID_RESPONSE", usage_unknown=True)
        return result

    def _safe_id(self, value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            return None
        if self._settings.NINE_ROUTER_API_KEY.get_secret_value() in value:
            return None
        if any(ord(char) < 32 for char in value):
            return None
        return value.strip()

    async def discover_models(self) -> tuple[str, ...]:
        document = self._document(await self._request("GET", "/models"))
        data = document.get("data")
        if not isinstance(data, list):
            raise ProviderFailure("PROVIDER_INVALID_RESPONSE")
        models = {
            model_id
            for item in data
            if isinstance(item, dict)
            and item.get("active", True) is not False
            and (model_id := self._safe_id(item.get("id"))) is not None
        }
        if not models:
            raise ProviderFailure("PROVIDER_MODEL_UNAVAILABLE")
        return tuple(sorted(models))

    def select_model(self, policy_ref: str, models: tuple[str, ...]) -> str:
        override = str(
            getattr(self._settings, _POLICY_MODELS.get(policy_ref, "NINE_ROUTER_MODEL_DEFAULT"))
        ).strip()
        configured = override or self._settings.NINE_ROUTER_MODEL_DEFAULT.strip()
        if configured:
            if configured not in models:
                raise ProviderFailure("PROVIDER_MODEL_UNAVAILABLE")
            return configured
        if len(models) == 1:
            return models[0]
        raise ProviderFailure("MODEL_SELECTION_REQUIRED")

    async def readiness(self, *, policy_ref: str = "ara.production") -> ProviderReadiness:
        if not self._configured():
            return ProviderReadiness(
                status="MISCONFIGURED", error_code="PROVIDER_CONFIGURATION_MISSING"
            )
        models: tuple[str, ...] = ()
        try:
            models = await self.discover_models()
            selected = self.select_model(policy_ref, models)
        except ProviderFailure as exc:
            auth = exc.code == "PROVIDER_AUTHENTICATION_FAILED"
            selection = exc.code == "MODEL_SELECTION_REQUIRED"
            return ProviderReadiness(
                status="AUTH_FAILED"
                if auth
                else "MODEL_SELECTION_REQUIRED"
                if selection
                else "UNAVAILABLE",
                configured=True,
                reachable=auth or bool(models),
                authenticated=bool(models),
                available_model_ids=models,
                error_code=exc.code,
            )
        return ProviderReadiness(
            status="CONNECTED",
            configured=True,
            reachable=True,
            authenticated=True,
            model_selected=True,
            available_model_ids=models,
            selected_model_id=selected,
        )

    async def complete(self, request: ModelRequest, *, route_id: str) -> ModelResponse:
        started = monotonic()
        status = "FAILED"
        result: ModelResponse | None = None
        try:
            model = self.select_model(request.policy_ref, await self.discover_models())
            document_response = await self._request(
                "POST",
                "/chat/completions",
                body={
                    "model": model,
                    "messages": list(request.messages),
                    "max_tokens": request.requested_max_tokens,
                    "stream": False,
                },
            )
            document = self._document(document_response)
            choices = document.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise ProviderFailure("PROVIDER_INVALID_RESPONSE", usage_unknown=True)
            message = choices[0].get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if (
                not isinstance(content, str)
                or not content.strip()
                or self._settings.NINE_ROUTER_API_KEY.get_secret_value() in content
            ):
                raise ProviderFailure("PROVIDER_INVALID_RESPONSE", usage_unknown=True)
            usage = document.get("usage")
            if not isinstance(usage, dict) or any(
                type(usage.get(key)) is not int or usage[key] < 0
                for key in ("prompt_tokens", "completion_tokens")
            ):
                # Integer usage is required by the existing runtime. Unknown is never fabricated.
                raise ProviderFailure("PROVIDER_USAGE_UNAVAILABLE", usage_unknown=True)
            cost = usage.get("cost", document.get("cost"))
            if cost is not None and (
                type(cost) not in {int, float} or not math.isfinite(cost) or cost < 0
            ):
                raise ProviderFailure("PROVIDER_INVALID_RESPONSE", usage_unknown=True)
            result = ModelResponse(
                content=content,
                route_id=route_id,
                input_tokens=usage["prompt_tokens"],
                output_tokens=usage["completion_tokens"],
                cost=cost,
                provider_request_id=self._safe_id(document.get("id"))
                or self._safe_id(document_response.headers.get("x-request-id")),
            )
            status = "COMPLETED"
            return result
        finally:
            # Deliberately exclude URL, messages, exception repr, model account, and headers.
            logger.info(
                "model_transport",
                extra={
                    "run_id": request.run_id,
                    "correlation_id": request.correlation_id,
                    "route_id": route_id,
                    "status": status,
                    "provider_request_id": result.provider_request_id if result else None,
                    "input_tokens": result.input_tokens if result else None,
                    "output_tokens": result.output_tokens if result else None,
                    "latency_milliseconds": int((monotonic() - started) * 1000),
                },
            )
