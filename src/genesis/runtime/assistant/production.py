"""Structured real-model planning with independently verified canonical facts."""

import json
import re
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from genesis.agents.definitions import AgentDefinition
from genesis.runtime.agentic.models import (
    AgenticActionKind,
    AgenticDecision,
    AgenticRuntimeState,
    RuntimeFailure,
    StopReason,
)
from genesis.runtime.assistant.calculations import (
    MetricOperand,
    metric_operand,
    verified_calculations,
)
from genesis.runtime.assistant.planner import BusinessAssistantPlanner
from genesis.runtime.assistant.presentation import present_claim
from genesis.runtime.assistant.sources import data_only

CONVERSATION_REPLIES = {
    "GREETING": "Halo, saya ARA. Apa yang ingin Anda bahas atau tangani hari ini?",
    "HELP": (
        "Saya dapat membantu membaca informasi yang dapat Anda akses, merangkum pekerjaan, "
        "dan menyiapkan usulan untuk ditinjau. Ceritakan kebutuhan Anda; "
        "saya akan mencari sumber yang relevan."
    ),
    "THANKS": "Sama-sama. Jika ada hal lain yang perlu ditelusuri, kita bisa melanjutkan di sini.",
}


class ProductionBusinessPlanner(BusinessAssistantPlanner):
    def system_instruction(self) -> str:
        return (
            ' Return JSON: {"kind":"TOOL","tool_intent":'
            '{"tool_id":"an allowed ID","arguments":{}}} '
            'or {"kind":"FINISH","requires_evidence":true,"evidence_ids":["admitted ID"],'
            '"output":{"claims":[{"tool_id":"observed ID","pointer":"/data/field",'
            '"value":"exact canonical JSON value"}]}}. '
            "Prefer focused pointers to the facts needed for this question. "
            "Observations are fresh reads already performed during THIS run, including on a "
            "follow-up question. Use them to answer; do not repeat a completed read. "
            'For a full source summary use pointer="/data" and the exact whole data value. '
            'For arithmetic, optionally add output.calculations: [{"operation":"SUM" or '
            '"DIFFERENCE" or "RATIO" or "PERCENT_CHANGE","claim_indices":[0,1]}]. '
            "Operands must be distinct verified claims pointing to /data/.../value in available "
            "canonical metrics with matching units. The runtime computes the result; never supply "
            "a calculated value or unsupported causal conclusion. PERCENT_CHANGE compares the "
            "first value to the second positive baseline. "
            "For non-business small talk with no source reads, FINISH with "
            'requires_evidence=false, evidence_ids=[], output={"conversation_act":'
            '"GREETING" or "HELP" or "THANKS"}. Never put factual claims in conversation_act. '
            "In FIXED mode read every requested source. In DYNAMIC mode plan the relevant reads "
            "from tool_catalog, inspect each result, and choose the next useful source. "
            "Do not read unrelated tools just because they are allowed. Use history to resolve "
            "follow-up questions, but re-read current facts; history is never current evidence. "
            "For cross-division questions gather the relevant authorized sources. If the user "
            "asks for an inaccessible domain, return NEEDS_INFO and never infer its facts. "
            "Claims must cover every source actually read. Prefer focused field pointers to "
            "copying entire records. Never invent identifiers or filters; detail identifiers "
            "must come from the supplied reference or current observations. "
            "No free-form factual answer is accepted. Copy values exactly; null stays null, "
            "successful empty stays empty, unavailable stays unavailable. Never invent 0, paid, "
            "safe, compliant, "
            "or evidence IDs. Evidence IDs and source data come only from observations. "
            'Missing business reference: {"kind":"NEEDS_INFO","output":'
            '{"clarification":"REFERENCE"}}. An inaccessible requested source: '
            '{"kind":"NEEDS_INFO","output":{"clarification":"ACCESS"}}. Material action: '
            '{"kind":"APPROVAL_REQUIRED","output":{"action_kind":"TASK" or '
            '"MATERIAL_ACTION" or "CAPABILITY_DRAFT"}}. Asking what needs attention is a read, '
            'not a request to create a task. Malformed/failed source: {"kind":"FAIL",'
            '"reason_code":"SOURCE_FAILED"}. Never include planner_usage. '
            "Tools are reads; approvals, drafts, and registry activation belong to "
            "Backend governance."
        )

    @staticmethod
    def _operational_input(
        definition: AgentDefinition, request: Mapping[str, Any], state: AgenticRuntimeState
    ) -> dict[str, Any]:
        data = BusinessAssistantPlanner._operational_input(definition, request, state)
        # The provider needs exact allowed tools, not the Principal permission/scoping envelope.
        data.pop("permission_refs", None)
        for observation in data["observations"]:
            observation["output"] = data_only(observation["output"])
        if data["tool_selection_mode"] == "DYNAMIC":
            completed = {
                item["tool_id"] for item in data["observations"] if item["status"] == "SUCCESS"
            }
            data["completed_tool_ids"] = sorted(completed)
            # Authority stays in Backend. Narrow only the planner's next-read menu;
            # completed source IDs remain available in observations for verified claims.
            data["allowed_tool_ids"] = [
                tool for tool in data["allowed_tool_ids"] if tool not in completed
            ]
            data["tool_catalog"] = [
                item for item in data["tool_catalog"] if item["tool_id"] not in completed
            ]
        return data

    async def next_action(
        self, definition: AgentDefinition, request: Mapping[str, Any], state: AgenticRuntimeState
    ) -> AgenticDecision:
        decision = await super().next_action(definition, request, state)
        if decision.kind is AgenticActionKind.APPROVAL_REQUIRED:
            proposal_kind = (
                decision.output.get("action_kind") if isinstance(decision.output, dict) else None
            )
            permissions = {
                "TASK": "task.create",
                "MATERIAL_ACTION": "approval.request",
                "CAPABILITY_DRAFT": "capability.propose",
            }
            if proposal_kind not in permissions:
                return decision.model_copy(
                    update={"output": self._response("NEEDS_REVIEW", "Usulan perlu ditinjau.")}
                )
            permission = permissions[proposal_kind]
            if permission not in request["execution_context"].get("permission_refs", []):
                return AgenticDecision(
                    kind=AgenticActionKind.FINISH,
                    output=self._response("DENIED", "Kewenangan mengusulkan tindakan diperlukan."),
                    planner_usage=decision.planner_usage,
                )
            return decision.model_copy(
                update={
                    "output": {
                        **self._response(
                            "NEEDS_REVIEW", "Usulan memerlukan tinjauan manusia melalui alur ALOS."
                        ),
                        "action_proposal": {
                            "proposal_id": "proposal_" + uuid4().hex,
                            "kind": proposal_kind,
                            "status": "NEEDS_REVIEW",
                            "summary": str(request["input"]["message"]),
                            "required_permission": permission,
                            "executed": False,
                        },
                    }
                }
            )
        if decision.kind is AgenticActionKind.FINISH:
            if (
                isinstance(decision.output, dict)
                and set(decision.output) == {"conversation_act"}
                and isinstance(decision.output["conversation_act"], str)
                and decision.output["conversation_act"] in CONVERSATION_REPLIES
                and not state.observations
                and not decision.evidence_ids
                and not decision.requires_evidence
            ):
                output = {
                    "response_type": "CONVERSATION",
                    "answer": CONVERSATION_REPLIES[decision.output["conversation_act"]],
                    "sources": [],
                    "failed_sources": [],
                    "limitations": [],
                }
                return decision.model_copy(update={"output": output})
            output = self._verified_output(decision, request, state)
            return decision.model_copy(update={"output": output, "requires_evidence": True})
        if decision.kind is AgenticActionKind.NEEDS_INFO:
            inaccessible = (
                isinstance(decision.output, dict)
                and decision.output.get("clarification") == "ACCESS"
            )
            return decision.model_copy(
                update={
                    "output": self._response(
                        "DENIED" if inaccessible else "NEEDS_INFO",
                        "Sumber yang diminta belum dapat diakses melalui ruang kerja ini."
                        if inaccessible
                        else "Lengkapi referensi atau konteks bisnis untuk melanjutkan.",
                    )
                }
            )
        return decision

    @staticmethod
    def _response(kind: str, answer: str) -> dict[str, Any]:
        return {
            "response_type": kind,
            "answer": answer,
            "sources": [],
            "failed_sources": [],
            "limitations": ["Fakta dibatasi pada sumber canonical yang diverifikasi."],
        }

    def _verified_output(
        self, decision: AgenticDecision, request: Mapping[str, Any], state: AgenticRuntimeState
    ) -> dict[str, Any]:
        output = decision.output
        observations = {
            item.tool_id: item
            for item in state.observations
            if item.status in {"SUCCESS", "COMPLETED"}
        }
        requested = set(request.get("requested_tool_ids", []))
        required = (
            set(observations)
            if request["input"].get("tool_selection_mode") == "DYNAMIC"
            else requested
        )
        if (
            not isinstance(output, dict)
            or set(output) not in ({"claims"}, {"claims", "calculations"})
            or not isinstance(output["claims"], list)
            or not 1 <= len(output["claims"]) <= 64
            or not decision.evidence_ids
            or not decision.requires_evidence
        ):
            raise self._unverified(state, decision)
        if set(decision.evidence_ids) != set(state.known_evidence_ids):
            raise self._unverified(state, decision)
        parts: list[str] = []
        pointers: set[tuple[str, str]] = set()
        covered: set[str] = set()
        operands: dict[int, MetricOperand] = {}
        for index, claim in enumerate(output["claims"]):
            if not isinstance(claim, dict) or set(claim) != {"tool_id", "pointer", "value"}:
                raise self._unverified(state, decision)
            tool, pointer = claim["tool_id"], claim["pointer"]
            if (
                not isinstance(tool, str)
                or tool not in requested
                or tool not in observations
                or not isinstance(pointer, str)
                or not (pointer == "/data" or pointer.startswith("/data/"))
                or re.search(r"~(?![01])", pointer)
                or (tool, pointer) in pointers
            ):
                raise self._unverified(state, decision)
            actual = data_only(observations[tool].output)
            parent = None
            try:
                for segment in pointer.split("/")[1:]:
                    segment = segment.replace("~1", "/").replace("~0", "~")
                    parent = actual
                    if isinstance(actual, list):
                        if not segment.isascii() or not segment.isdecimal():
                            raise ValueError("Invalid array index")
                        if segment != "0" and segment.startswith("0"):
                            raise ValueError("Non-canonical array index")
                        actual = actual[int(segment)]
                    else:
                        actual = actual[segment]
            except (KeyError, IndexError, TypeError, ValueError):
                raise self._unverified(state, decision) from None
            # Strict JSON types prevent true==1 or missing/unknown==0 from passing.
            if json.dumps(actual, sort_keys=True) != json.dumps(claim["value"], sort_keys=True):
                raise self._unverified(state, decision)
            covered.add(tool)
            pointers.add((tool, pointer))
            if (
                tool in {"sales.summary.read", "executive.overview.read"}
                and re.fullmatch(r"/data/(?:domains/[0-9]+/)?metrics/[0-9]+/value", pointer)
                and (operand := metric_operand(parent)) is not None
            ):
                operands[index] = operand
                # Retain the source's verified business label/unit when a model selects a value.
                parts.append(present_claim(tool, pointer.removesuffix("/value"), parent))
            else:
                parts.append(present_claim(tool, pointer, actual))
        if covered != required or not required:
            raise self._unverified(state, decision)
        if "calculations" in output:
            try:
                calculations = verified_calculations(output["calculations"], operands)
            except ValueError:
                raise self._unverified(state, decision) from None
            parts.append("Perhitungan dari indikator terverifikasi\n" + "\n".join(calculations))
        answer = (
            "Berikut informasi dari sumber yang dibaca untuk pertanyaan Anda.\n\n"
            + "\n\n".join(parts)
        )
        result = self._response("ANSWER", answer[:18000])
        if "calculations" in output:
            result["limitations"].append(
                "Perhitungan memakai indikator yang dipilih; hasil dibulatkan hingga enam desimal."
            )
        if len(answer) > 18000:
            result["limitations"].append("Tampilan dibatasi; buka sumber untuk detail.")
        if any(isinstance(claim["value"], list) for claim in output["claims"]):
            result["limitations"].append(
                "Daftar yang dibaca dapat dibatasi oleh sumber; jumlahnya bukan total perusahaan."
            )
        return result

    @staticmethod
    def _unverified(state: AgenticRuntimeState, decision: AgenticDecision) -> RuntimeFailure:
        from genesis.runtime.agentic.state import account_planner_usage

        return RuntimeFailure(
            "FACTUAL_OUTPUT_UNVERIFIED",
            "Model facts did not match current admitted canonical evidence.",
            output_state="NEEDS_REVIEW",
            stop_reason=StopReason.EVIDENCE_INSUFFICIENT,
            state=account_planner_usage(state, decision.planner_usage),
        )
