"""Offline transport, secret, discovery, and fail-closed provider proofs."""

import json
import logging
import traceback
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from genesis.adapters.providers.nine_router import NineRouterProviderAdapter, ProviderFailure
from genesis.config import Settings
from genesis.main import create_app
from genesis.model_gateway.budget import BudgetExceeded
from genesis.model_gateway.composition import build_model_gateway
from genesis.model_gateway.policy import ModelAccessDenied
from genesis.model_gateway.types import ModelRequest


def configuration(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        **{
            "DEFAULT_MODEL_ROUTE": "nine_router",
            "NINE_ROUTER_BASE_URL": "http://router.test/custom/v1",
            "NINE_ROUTER_API_KEY": SecretStr(uuid4().hex),
            **overrides,
        },
    )


def model_request(**overrides: object) -> ModelRequest:
    return ModelRequest.model_validate(
        {
            "run_id": "run_provider",
            "correlation_id": "corr_provider",
            "policy_ref": "policy.standard",
            "purpose": "structured decision",
            "messages": ({"role": "user", "content": "Read source"},),
            "requested_max_tokens": 70,
            "budget": {"max_tokens": 100},
            **overrides,
        }
    )


def completion(**overrides: object) -> dict:
    return {
        "id": "request_transport",
        "choices": [{"message": {"content": "structured content"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        **overrides,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "policy_ref, authenticated, expected_status, expected_readiness",
    [
        ("policy.standard", True, 200, "CONNECTED"),
        ("policy.fast", True, 200, "MODEL_SELECTION_REQUIRED"),
        ("unapproved.policy", True, 422, None),
        ("policy.standard", False, 401, None),
    ],
)
async def test_internal_readiness_checks_selected_policy_and_service_authentication(
    policy_ref: str, authenticated: bool, expected_status: int, expected_readiness: str | None
) -> None:
    token = uuid4().hex
    app = create_app(
        configuration(ALOS_INTERNAL_TOKEN=token, NINE_ROUTER_MODEL_STANDARD="fixture-standard")
    )
    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"data": [{"id": "fixture-standard"}, {"id": "fixture-fast"}]}
                )
            )
        ) as provider,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://genesis.test"
        ) as client,
    ):
        app.state.provider_http_client = provider
        result = await client.get(
            "/internal/v1/models/readiness",
            params={"policy_ref": policy_ref},
            headers={"Authorization": "Bearer " + token} if authenticated else {},
        )
    assert result.status_code == expected_status
    if expected_readiness is not None:
        assert result.json()["status"] == expected_readiness
        assert result.json()["model_selected"] is (expected_readiness == "CONNECTED")
    assert (
        token not in result.text
        and app.state.settings.NINE_ROUTER_API_KEY.get_secret_value() not in result.text
    )


@pytest.mark.asyncio
async def test_completion_preserves_transport_and_authoritative_telemetry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = configuration()
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert (
            request.headers["Authorization"]
            == "Bearer " + config.NINE_ROUTER_API_KEY.get_secret_value()
        )
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "fixture-model"}]})
        assert str(request.url) == "http://router.test/custom/v1/chat/completions"
        assert json.loads(request.content) == {
            "model": "fixture-model",
            "messages": [{"role": "user", "content": "Read source"}],
            "max_tokens": 70,
            "stream": False,
        }
        return httpx.Response(
            200, json=completion(usage={"prompt_tokens": 10, "completion_tokens": 20, "cost": 0.02})
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with caplog.at_level(logging.INFO):
            result = await NineRouterProviderAdapter(config, client=client).complete(
                model_request(), route_id="nine_router"
            )
    assert len(seen) == 2 and result.content == "structured content"
    assert result.route_id == "nine_router" and result.provider_request_id == "request_transport"
    assert result.input_tokens == 10 and result.output_tokens == 20 and result.cost == 0.02
    record = next(item for item in caplog.records if item.msg == "model_transport")
    assert record.status == "COMPLETED" and record.latency_milliseconds >= 0
    assert config.NINE_ROUTER_API_KEY.get_secret_value() not in str(record.__dict__) + repr(config)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body_id, header_id, expected",
    [("body-id", "header-id", "body-id"), (None, "header-id", "header-id"), (None, None, None)],
)
async def test_optional_cost_and_request_id_are_never_fabricated(
    body_id: str | None, header_id: str | None, expected: str | None
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"id": "fixture-model"}]}
            if request.method == "GET"
            else completion(id=body_id),
            headers={"x-request-id": header_id} if header_id else {},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await NineRouterProviderAdapter(configuration(), client=client).complete(
            model_request(), route_id="nine_router"
        )
    assert result.cost is None and result.provider_request_id == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, code, attempts",
    [
        (400, "PROVIDER_INVALID_REQUEST", 1),
        (401, "PROVIDER_AUTHENTICATION_FAILED", 1),
        (403, "PROVIDER_AUTHENTICATION_FAILED", 1),
        (404, "PROVIDER_MODEL_UNAVAILABLE", 1),
        (422, "PROVIDER_INVALID_REQUEST", 1),
        (429, "PROVIDER_RATE_LIMITED", 2),
        (500, "PROVIDER_UNAVAILABLE", 1),
        (502, "PROVIDER_UNAVAILABLE", 2),
        (503, "PROVIDER_UNAVAILABLE", 2),
        (504, "PROVIDER_UNAVAILABLE", 2),
    ],
)
async def test_http_failures_have_bounded_retries_and_safe_diagnostics(
    status: int, code: str, attempts: int, caplog: pytest.LogCaptureFixture
) -> None:
    config = configuration()
    secret = config.NINE_ROUTER_API_KEY.get_secret_value()
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "fixture-model"}]})
        calls.append(request)
        return httpx.Response(status, text=secret)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderFailure, match=code) as failure:
            await NineRouterProviderAdapter(config, client=client).complete(
                model_request(), route_id="nine_router"
            )
    assert len(calls) == attempts
    assert (
        secret
        not in str(failure.value)
        + repr(failure.value)
        + "".join(traceback.format_exception(failure.value))
        + caplog.text
    )
    assert failure.value.__cause__ is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 502, 503, 504])
async def test_successful_retry_cannot_certify_usage_of_earlier_inference(status: int) -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "fixture-model"}]})
        calls.append(request)
        return httpx.Response(status) if len(calls) == 1 else httpx.Response(200, json=completion())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderFailure, match="PROVIDER_USAGE_UNAVAILABLE") as failure:
            await NineRouterProviderAdapter(configuration(), client=client).complete(
                model_request(), route_id="nine_router"
            )
    assert len(calls) == 2 and failure.value.usage_unknown


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.ConnectError, httpx.ReadError])
async def test_transport_failure_cannot_leak_secret_or_repeat_ambiguous_inference(
    error: type[httpx.TransportError],
) -> None:
    config = configuration()
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "fixture-model"}]})
        calls.append(request)
        raise error(config.NINE_ROUTER_API_KEY.get_secret_value(), request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderFailure) as failure:
            await NineRouterProviderAdapter(config, client=client).complete(
                model_request(), route_id="nine_router"
            )
    assert len(calls) == (2 if error is httpx.ConnectError else 1)
    assert failure.value.usage_unknown is (error is not httpx.ConnectError)
    assert config.NINE_ROUTER_API_KEY.get_secret_value() not in "".join(
        traceback.format_exception(failure.value)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "document",
    [
        {},
        {"choices": []},
        {"choices": [None]},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": ""}}]},
        completion(usage=None),
        completion(usage={"prompt_tokens": True, "completion_tokens": 1}),
        completion(usage={"prompt_tokens": -1, "completion_tokens": 1}),
        completion(cost=-1),
        completion(cost=float("inf")),
    ],
)
async def test_invalid_completion_and_unknown_usage_fail_before_planning(document: dict) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "fixture-model"}]})
        return httpx.Response(
            200, content=json.dumps(document), headers={"content-type": "application/json"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderFailure):
            await NineRouterProviderAdapter(configuration(), client=client).complete(
                model_request(), route_id="nine_router"
            )


@pytest.mark.asyncio
async def test_invalid_json_is_typed_and_does_not_preserve_raw_payload() -> None:
    config = configuration()

    def handle(request: httpx.Request) -> httpx.Response:
        return (
            httpx.Response(200, json={"data": [{"id": "fixture-model"}]})
            if request.method == "GET"
            else httpx.Response(200, text=config.NINE_ROUTER_API_KEY.get_secret_value())
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderFailure, match="PROVIDER_INVALID_RESPONSE"):
            await NineRouterProviderAdapter(config, client=client).complete(
                model_request(), route_id="nine_router"
            )


@pytest.mark.parametrize(
    "policy, field",
    [
        ("policy.fast", "FAST"),
        ("policy.standard", "STANDARD"),
        ("ara.production", "STANDARD"),
        ("policy.reasoning", "REASONING"),
        ("policy.evidence-bound-research.v1", "REASONING"),
        ("policy.coding", "CODING"),
        ("policy.critical", "CRITICAL"),
    ],
)
def test_policy_overrides_have_precedence_over_default(policy: str, field: str) -> None:
    adapter = NineRouterProviderAdapter(
        configuration(
            NINE_ROUTER_MODEL_DEFAULT="default-alias",
            **{f"NINE_ROUTER_MODEL_{field}": "policy-alias"},
        )
    )
    assert adapter.select_model(policy, ("default-alias", "policy-alias")) == "policy-alias"


@pytest.mark.parametrize(
    "models, default, expected",
    [
        (("single",), "", "single"),
        (("alpha", "beta"), "beta", "beta"),
        (("alpha", "beta"), "", "MODEL_SELECTION_REQUIRED"),
        (("alpha",), "unknown", "PROVIDER_MODEL_UNAVAILABLE"),
    ],
)
def test_model_selection_never_invents_or_selects_first_model(
    models: tuple[str, ...], default: str, expected: str
) -> None:
    adapter = NineRouterProviderAdapter(configuration(NINE_ROUTER_MODEL_DEFAULT=default))
    if expected in {"MODEL_SELECTION_REQUIRED", "PROVIDER_MODEL_UNAVAILABLE"}:
        with pytest.raises(ProviderFailure, match=expected):
            adapter.select_model("policy.standard", models)
    else:
        assert adapter.select_model("policy.standard", models) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, models, expected",
    [
        (200, ["single"], "CONNECTED"),
        (200, ["alpha", "beta"], "MODEL_SELECTION_REQUIRED"),
        (200, [], "UNAVAILABLE"),
        (401, [], "AUTH_FAILED"),
        (403, [], "AUTH_FAILED"),
        (503, [], "UNAVAILABLE"),
    ],
)
async def test_authoritative_readiness(status: int, models: list[str], expected: str) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(status, json={"data": [{"id": model} for model in models]})
        )
    ) as client:
        readiness = await NineRouterProviderAdapter(configuration(), client=client).readiness()
    assert readiness.status == expected
    assert readiness.model_selected == (expected == "CONNECTED")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"NINE_ROUTER_API_KEY": SecretStr("")},
        {"DEFAULT_MODEL_ROUTE": "disabled"},
        {"NINE_ROUTER_BASE_URL": ""},
    ],
)
async def test_configuration_or_kill_switch_fails_without_any_http(overrides: dict) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("HTTP must not run"))
    ) as client:
        provider = NineRouterProviderAdapter(configuration(**overrides), client=client)
        assert (await provider.readiness()).status == "MISCONFIGURED"
        with pytest.raises(ProviderFailure, match="PROVIDER_CONFIGURATION_MISSING"):
            await provider.complete(model_request(), route_id="nine_router")


@pytest.mark.parametrize(
    "url",
    [
        "http://user:password@router.test/v1",
        "http://router.test/v1?key=secret",
        "http://router.test/v1#credential",
        "ftp://router.test/v1",
    ],
)
def test_configuration_rejects_credentials_and_non_http_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        configuration(NINE_ROUTER_BASE_URL=url)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation, failure",
    [
        ("classification", ModelAccessDenied),
        ("policy", ModelAccessDenied),
        ("budget", BudgetExceeded),
    ],
)
async def test_gateway_policy_and_budget_reject_before_provider(
    mutation: str, failure: type[Exception]
) -> None:
    overrides = (
        {"data_classification": "RESTRICTED"}
        if mutation == "classification"
        else {"policy_ref": "unknown"}
        if mutation == "policy"
        else {"requested_max_tokens": 101}
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("Provider must not run"))
    ) as client:
        with pytest.raises(failure):
            await build_model_gateway(configuration(), client=client).complete(
                model_request(**overrides)
            )


@pytest.mark.asyncio
async def test_reported_usage_over_budget_is_not_admitted() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"id": "single"}]}
            if request.method == "GET"
            else completion(usage={"prompt_tokens": 90, "completion_tokens": 70}),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(BudgetExceeded):
            await build_model_gateway(configuration(), client=client).complete(model_request())
