"""Structured real-model planning with independently verified canonical facts."""

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
from genesis.runtime.assistant.planner import BusinessAssistantPlanner
from genesis.runtime.assistant.sources import data_only, display


class ProductionBusinessPlanner(BusinessAssistantPlanner):
    def system_instruction(self) -> str:
        return (
            ' Return JSON: {"kind":"TOOL","tool_intent":'
            '{"tool_id":"an allowed ID","arguments":{}}} '
            'or {"kind":"FINISH","requires_evidence":true,"evidence_ids":["admitted ID"],'
            '"output":{"claims":[{"tool_id":"observed ID","pointer":"/data/field",'
            '"value":"exact canonical JSON value"}]}}. '
            'For a source summary use pointer="/data" and the exact whole data value. '
            "Read every requested source before FINISH. Claims must cover every requested source. "
            "No free-form factual answer is accepted. Copy values exactly; null stays null, "
            "successful empty stays empty, unavailable stays unavailable. Never invent 0, paid, "
            "safe, compliant, "
            "or evidence IDs. Evidence IDs and source data come only from observations. "
            'Missing business reference: {"kind":"NEEDS_INFO"}. Material action: '
            '{"kind":"APPROVAL_REQUIRED"}. Malformed/failed source: {"kind":"FAIL",'
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
        return data

    async def next_action(
        self, definition: AgentDefinition, request: Mapping[str, Any], state: AgenticRuntimeState
    ) -> AgenticDecision:
        message = str(request["input"]["message"])
        text = message.casefold()
        material = any(
            word in text
            for word in ("bayar vendor", "approve budget", "jual unit", "aktifkan pricing")
        )
        factory = "buat agent" in text
        task = any(word in text for word in ("buat task", "buat tugas", "tindak lanjut"))
        if material or factory or task:
            permission = (
                "approval.request"
                if material
                else "capability.propose"
                if factory
                else "task.create"
            )
            if task and permission not in request["execution_context"].get("permission_refs", []):
                return AgenticDecision(
                    kind=AgenticActionKind.FINISH,
                    output=self._response("DENIED", "Kewenangan task.create diperlukan."),
                )
            return AgenticDecision(
                kind=AgenticActionKind.APPROVAL_REQUIRED,
                output={
                    **self._response(
                        "NEEDS_REVIEW", "Usulan memerlukan tinjauan manusia melalui alur ALOS."
                    ),
                    "action_proposal": {
                        "proposal_id": "proposal_" + uuid4().hex,
                        "kind": "MATERIAL_ACTION"
                        if material
                        else "CAPABILITY_DRAFT"
                        if factory
                        else "TASK",
                        "status": "NEEDS_REVIEW",
                        "summary": message,
                        "required_permission": permission,
                        "executed": False,
                    },
                },
            )
        decision = await super().next_action(definition, request, state)
        if decision.kind is AgenticActionKind.FINISH:
            output = self._verified_output(decision, request, state)
            return decision.model_copy(update={"output": output, "requires_evidence": True})
        if decision.kind in {AgenticActionKind.NEEDS_INFO, AgenticActionKind.APPROVAL_REQUIRED}:
            return decision.model_copy(
                update={
                    "output": self._response(
                        "NEEDS_INFO"
                        if decision.kind is AgenticActionKind.NEEDS_INFO
                        else "NEEDS_REVIEW",
                        "Lengkapi referensi atau konteks bisnis untuk melanjutkan."
                        if decision.kind is AgenticActionKind.NEEDS_INFO
                        else "Usulan memerlukan tinjauan manusia.",
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
        if (
            not isinstance(output, dict)
            or set(output) != {"claims"}
            or not isinstance(output["claims"], list)
            or not decision.evidence_ids
            or not decision.requires_evidence
        ):
            raise self._unverified(state, decision)
        if set(decision.evidence_ids) != set(state.known_evidence_ids):
            raise self._unverified(state, decision)
        parts: list[str] = []
        covered: set[str] = set()
        for claim in output["claims"]:
            if not isinstance(claim, dict) or set(claim) != {"tool_id", "pointer", "value"}:
                raise self._unverified(state, decision)
            tool, pointer = claim["tool_id"], claim["pointer"]
            if (
                not isinstance(tool, str)
                or tool not in requested
                or tool not in observations
                or not isinstance(pointer, str)
                or not pointer.startswith("/data")
            ):
                raise self._unverified(state, decision)
            actual = data_only(observations[tool].output)
            try:
                for token in pointer.split("/")[1:]:
                    token = token.replace("~1", "/").replace("~0", "~")
                    actual = actual[int(token)] if isinstance(actual, list) else actual[token]
            except (KeyError, IndexError, TypeError, ValueError):
                raise self._unverified(state, decision) from None
            # Strict JSON types prevent true==1 or missing/unknown==0 from passing.
            import json

            if json.dumps(actual, sort_keys=True) != json.dumps(claim["value"], sort_keys=True):
                raise self._unverified(state, decision)
            covered.add(tool)
            parts.append(tool + pointer + "\n" + display(actual))
        if covered != requested or not requested:
            raise self._unverified(state, decision)
        answer = "\n\n".join(parts)
        result = self._response("ANSWER", answer[:18000])
        if len(answer) > 18000:
            result["limitations"].append("Tampilan dibatasi; buka sumber untuk detail.")
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
