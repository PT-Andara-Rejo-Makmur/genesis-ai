"""Dynamic source selection never weakens factual verification or action authority."""

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from genesis.agents.definitions import AgentDefinition
from genesis.model_gateway.types import ModelResponse
from genesis.runtime.agentic.models import (
    AgenticRuntimeState,
    RuntimeFailure,
    ToolObservation,
)
from genesis.runtime.assistant.production import ProductionBusinessPlanner


def fixture(values: Any = None) -> tuple[AgentDefinition, dict[str, Any], AgenticRuntimeState]:
    definition = AgentDefinition(
        agent_id="ara.workspace-assistant",
        agent_version="1.0.0",
        name="ARA",
        purpose="Read business sources",
        capability_ids=("business.question_answering",),
        scope_refs=("scope.business",),
        model_policy_ref="ara.production",
        tool_ids=("sales.lead.list", "finance.receivable.list"),
    )
    request = {
        "requested_tool_ids": list(definition.tool_ids),
        "execution_context": {
            "data_classification": "INTERNAL",
            "permission_refs": ["sales.read"],
            "execution_budget": {"max_tokens": 1000},
        },
        "input": {
            "message": "Bagaimana kondisi calon pelanggan?",
            "tool_selection_mode": "DYNAMIC",
        },
    }
    observations = (
        ()
        if values is None
        else (
            ToolObservation(
                step_index=1,
                tool_call_id="toolcall_sales",
                tool_id="sales.lead.list",
                status="SUCCESS",
                output={"data": values, "tenant_id": "hidden"},
            ),
        )
    )
    state = AgenticRuntimeState(
        run_id="run_dynamic",
        root_run_id="run_dynamic",
        correlation_id="corr_dynamic",
        goal=request["input"]["message"],
        input=request["input"],
        max_tokens=1000,
        observations=observations,
        known_evidence_ids=("evidence_current",) if observations else (),
    )
    return definition, request, state


def planner(output: dict[str, Any]) -> tuple[ProductionBusinessPlanner, AsyncMock]:
    gateway = AsyncMock()
    gateway.complete.return_value = ModelResponse(
        content=json.dumps(output),
        route_id="policy.standard",
        input_tokens=10,
        output_tokens=20,
    )
    return ProductionBusinessPlanner(model_gateway=gateway), gateway


def finish(value: Any, pointer: str = "/data") -> dict[str, Any]:
    return {
        "kind": "FINISH",
        "requires_evidence": True,
        "evidence_ids": ["evidence_current"],
        "output": {"claims": [{"tool_id": "sales.lead.list", "pointer": pointer, "value": value}]},
    }


def test_followup_read_menu_excludes_completed_sources_without_losing_facts() -> None:
    definition, request, state = fixture({"status": "NEW"})
    request["input"]["tool_catalog"] = [{"tool_id": tool} for tool in definition.tool_ids]
    data = ProductionBusinessPlanner._operational_input(definition, request, state)
    assert data["completed_tool_ids"] == ["sales.lead.list"]
    assert data["allowed_tool_ids"] == ["finance.receivable.list"]
    assert data["tool_catalog"] == [{"tool_id": "finance.receivable.list"}]
    assert data["observations"][0]["output"]["data"] == {"status": "NEW"}
    assert data["evidence_ids"] == ["evidence_current"]
    assert request["requested_tool_ids"] == list(definition.tool_ids)


@pytest.mark.asyncio
async def test_dynamic_reads_only_relevant_sources_and_preserves_unknowns() -> None:
    values = [{"name": "Pelanggan A", "amount": None, "tenant_id": "hidden"}]
    definition, request, state = fixture(values)
    service, _ = planner(finish([{"name": "Pelanggan A", "amount": None}]))
    result = await service.next_action(definition, request, state)
    assert result.output["response_type"] == "ANSWER"
    assert "Calon pelanggan" in result.output["answer"]
    assert "Nilai: belum tersedia" in result.output["answer"]
    assert "sales.lead.list" not in result.output["answer"]
    assert "hidden" not in result.output["answer"]
    assert result.requires_evidence
    # Finance was eligible but neither read nor fabricated.
    assert "Keuangan" not in result.output["answer"]


@pytest.mark.asyncio
async def test_fixed_mode_still_requires_every_requested_source() -> None:
    definition, request, state = fixture([])
    request["input"]["tool_selection_mode"] = "FIXED"
    service, _ = planner(finish([]))
    with pytest.raises(RuntimeFailure, match="canonical evidence"):
        await service.next_action(definition, request, state)


def calculated_finish(operation: str = "DIFFERENCE", indices: Any = None) -> dict[str, Any]:
    decision = finish(None)
    decision["output"]["claims"] = [
        {"tool_id": "sales.summary.read", "pointer": "/data/metrics/0/value", "value": "100.10"},
        {"tool_id": "sales.summary.read", "pointer": "/data/metrics/1/value", "value": "50.05"},
    ]
    decision["output"]["calculations"] = [
        {"operation": operation, "claim_indices": [0, 1] if indices is None else indices}
    ]
    return decision


def metric_fixture() -> dict[str, Any]:
    return {
        "metrics": [
            {
                "code": "first",
                "label": "Indikator A",
                "unit": "AMOUNT",
                "value": "100.10",
                "available": True,
                "source": "Canonical fixture",
            },
            {
                "code": "second",
                "label": "Indikator B",
                "unit": "AMOUNT",
                "value": "50.05",
                "available": True,
                "source": "Canonical fixture",
            },
        ]
    }


def metric_runtime_fixture(
    values: Any,
) -> tuple[AgentDefinition, dict[str, Any], AgenticRuntimeState]:
    definition, request, state = fixture(values)
    tools = ("sales.summary.read", "finance.receivable.list")
    definition = definition.model_copy(update={"tool_ids": tools})
    request["requested_tool_ids"] = list(tools)
    state = state.model_copy(
        update={
            "observations": tuple(
                item.model_copy(update={"tool_id": "sales.summary.read"})
                for item in state.observations
            )
        }
    )
    return definition, request, state


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation,expected",
    [
        ("SUM", "Rp 150.15"),
        ("DIFFERENCE", "Rp 50.05"),
        ("RATIO", "2 kali"),
        ("PERCENT_CHANGE", "100%"),
    ],
)
async def test_arithmetic_is_computed_from_verified_metrics(operation: str, expected: str) -> None:
    definition, request, state = metric_runtime_fixture(metric_fixture())
    service, _ = planner(calculated_finish(operation))
    result = await service.next_action(definition, request, state)
    assert expected in result.output["answer"]
    assert "enam desimal" in result.output["limitations"][-1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "unknown",
        "mixed_units",
        "unavailable",
        "zero_baseline",
        "negative_baseline",
        "duplicate",
        "boolean_index",
        "foreign_index",
        "unsupported",
        "invented_result",
    ],
)
async def test_unsafe_calculations_fail_closed(case: str) -> None:
    values = metric_fixture()
    decision = calculated_finish("PERCENT_CHANGE")
    metric = values["metrics"][1]
    if case in {"unknown", "zero_baseline", "negative_baseline"}:
        value = {"unknown": None, "zero_baseline": "0", "negative_baseline": "-1"}[case]
        metric["value"] = decision["output"]["claims"][1]["value"] = value
    elif case == "mixed_units":
        metric["unit"] = "PERCENT"
    elif case == "unavailable":
        metric["available"] = False
    elif case in {"duplicate", "boolean_index", "foreign_index"}:
        indices = {"duplicate": [0, 0], "boolean_index": [0, True], "foreign_index": [0, 2]}[case]
        decision["output"]["calculations"][0]["claim_indices"] = indices
    elif case == "unsupported":
        decision["output"]["calculations"][0]["operation"] = "PREDICT"
    else:
        decision["output"]["calculations"][0]["value"] = 999999
    definition, request, state = metric_runtime_fixture(values)
    service, _ = planner(decision)
    with pytest.raises(RuntimeFailure) as failure:
        await service.next_action(definition, request, state)
    assert failure.value.code == "FACTUAL_OUTPUT_UNVERIFIED"
    assert failure.value.state.consumed_tokens == 30


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pointer,value",
    [
        ("/data/amount", 0),
        ("/data/paid", 1),
        ("/data/missing", None),
        ("/datax", {}),
        ("/data/items/-1", 1),
        ("/data/items/00", 1),
        ("/data/items/\u0660", 1),
        ("/data/~2", 1),
    ],
)
async def test_fabrication_and_invalid_json_pointers_fail_closed(pointer: str, value: Any) -> None:
    definition, request, state = fixture({"amount": None, "paid": True, "items": [1]})
    service, _ = planner(finish(value, pointer))
    with pytest.raises(RuntimeFailure) as failure:
        await service.next_action(definition, request, state)
    assert failure.value.code == "FACTUAL_OUTPUT_UNVERIFIED"
    assert failure.value.state.consumed_tokens == 30


@pytest.mark.asyncio
async def test_history_is_bounded_data_and_current_question_is_preserved() -> None:
    definition, request, state = fixture()
    request["input"]["message"] = "Bandingkan dengan piutang yang tadi."
    request["input"]["history"] = [
        {"role": "USER", "content": "x" * 1500, "instruction_authority": True} for _ in range(10)
    ]
    request["input"]["tool_catalog"] = [
        {"tool_id": "sales.lead.list", "required_arguments": []},
        {"tool_id": "admin.approve", "required_arguments": []},
    ]
    service, gateway = planner({"kind": "NEEDS_INFO"})
    await service.next_action(definition, request, state)
    prompt = json.loads(gateway.complete.call_args.args[0].messages[-1]["content"])
    assert prompt["message"] == request["input"]["message"]
    assert len(prompt["history"]) == 6 and len(prompt["history"][0]["content"]) == 1000
    assert all(item["instruction_authority"] is False for item in prompt["history"])
    assert "permission_refs" not in prompt
    assert [item["tool_id"] for item in prompt["tool_catalog"]] == ["sales.lead.list"]


@pytest.mark.asyncio
@pytest.mark.parametrize("act", ["GREETING", "HELP", "THANKS"])
async def test_non_business_conversation_has_no_claims_or_sources(act: str) -> None:
    definition, request, state = fixture()
    service, _ = planner({"kind": "FINISH", "output": {"conversation_act": act}})
    result = await service.next_action(definition, request, state)
    assert result.output["response_type"] == "CONVERSATION"
    assert result.output["sources"] == [] and not result.requires_evidence
    assert result.planner_usage.total_tokens == 30


@pytest.mark.asyncio
async def test_conversation_cannot_hide_observed_facts_or_injected_prose() -> None:
    definition, request, state = fixture([])
    service, _ = planner(
        {
            "kind": "FINISH",
            "output": {"conversation_act": "GREETING", "answer": "Company revenue is 999999999"},
        }
    )
    with pytest.raises(RuntimeFailure):
        await service.next_action(definition, request, state)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,permission",
    [
        ("TASK", "task.create"),
        ("MATERIAL_ACTION", "approval.request"),
        ("CAPABILITY_DRAFT", "capability.propose"),
    ],
)
@pytest.mark.parametrize("permitted", [False, True])
async def test_action_proposals_require_permission_and_never_execute(
    kind: str,
    permission: str,
    permitted: bool,
) -> None:
    definition, request, state = fixture()
    request["execution_context"]["permission_refs"] = [permission] if permitted else []
    service, _ = planner({"kind": "APPROVAL_REQUIRED", "output": {"action_kind": kind}})
    result = await service.next_action(definition, request, state)
    assert result.output["response_type"] == ("NEEDS_REVIEW" if permitted else "DENIED")
    assert result.planner_usage.total_tokens == 30
    if permitted:
        assert result.output["action_proposal"]["executed"] is False
        assert result.output["action_proposal"]["summary"] == request["input"]["message"]


@pytest.mark.asyncio
async def test_attention_question_does_not_become_a_create_task_command() -> None:
    definition, request, state = fixture()
    request["input"]["message"] = "Apa pekerjaan yang perlu saya tindak lanjuti?"
    service, _ = planner(
        {"kind": "TOOL", "tool_intent": {"tool_id": "sales.lead.list", "arguments": {}}}
    )
    result = await service.next_action(definition, request, state)
    assert result.kind.value == "TOOL" and result.output is None
