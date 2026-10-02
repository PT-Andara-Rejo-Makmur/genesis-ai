"""Deterministic adapter consumes structured observations as data, never as instructions."""

import json
from typing import Any
from uuid import uuid4

from genesis.model_gateway.types import ModelRequest, ModelResponse
from genesis.runtime.assistant.sources import display as display


class DeterministicBusinessAdapter:
    async def complete(self, request: ModelRequest, *, route_id: str) -> ModelResponse:
        inputs = json.loads(request.messages[-1]["content"])
        tools = inputs["allowed_tool_ids"]
        observations = inputs["observations"]
        base: dict[str, Any] = {
            "response_type": "ANSWER",
            "answer": "",
            "sources": [],
            "failed_sources": [],
            "limitations": [
                "Mode deterministik dengan skenario bisnis terdaftar.",
                "Production Model Provider: Belum Terhubung.",
            ],
        }
        message = inputs["message"].casefold()
        decision: dict[str, Any]
        if len(observations) < len(tools):
            decision = {
                "kind": "TOOL",
                "tool_intent": {
                    "tool_id": tools[len(observations)],
                    "arguments": inputs.get("tool_arguments", {}).get(tools[len(observations)], {}),
                },
            }
        elif tools:
            base["answer"] = "\n\n".join(
                f"{item['tool_id']}\n{display(item['output']['data'])}" for item in observations
            )
            if len(base["answer"]) > 18000:
                base["answer"] = base["answer"][:18000]
                base["limitations"].append(
                    "Tampilan diringkas karena batas ukuran; buka sumber untuk detail."
                )
            decision = {
                "kind": "FINISH",
                "output": base,
                "requires_evidence": True,
                "evidence_ids": inputs["evidence_ids"],
            }
        elif any(
            word in message
            for word in ("bayar vendor", "approve budget", "jual unit", "aktifkan pricing")
        ):
            base.update(
                response_type="NEEDS_REVIEW",
                answer="Tindakan material memerlukan keputusan manusia melalui alur approval ALOS.",
            )
            base["action_proposal"] = {
                "proposal_id": f"proposal_{uuid4().hex}",
                "kind": "MATERIAL_ACTION",
                "status": "NEEDS_REVIEW",
                "summary": inputs["message"],
                "required_permission": "approval.request",
                "executed": False,
            }
            decision = {"kind": "APPROVAL_REQUIRED", "output": base}
        elif any(word in message for word in ("buat task", "buat tugas", "tindak lanjut")):
            if "task.create" in inputs["permission_refs"]:
                base.update(
                    response_type="NEEDS_REVIEW",
                    answer=(
                        "Usulan task siap ditinjau. Task belum dibuat; "
                        "lengkapi detail melalui Shared Work."
                    ),
                )
                base["action_proposal"] = {
                    "proposal_id": f"proposal_{uuid4().hex}",
                    "kind": "TASK",
                    "status": "NEEDS_REVIEW",
                    "summary": inputs["message"],
                    "required_permission": "task.create",
                    "executed": False,
                }
                decision = {"kind": "APPROVAL_REQUIRED", "output": base}
            else:
                base.update(
                    response_type="DENIED",
                    answer="Kewenangan task.create diperlukan untuk mengusulkan task.",
                )
                decision = {"kind": "FINISH", "output": base}
        else:
            base.update(
                response_type="NEEDS_INFO",
                answer=(
                    "Jelaskan sumber bisnis yang ingin dibaca, misalnya lead Sales, "
                    "proyek aktif, piutang, atau incident IT."
                ),
            )
            decision = {"kind": "NEEDS_INFO", "output": base}
        return ModelResponse(
            content=json.dumps(decision),
            route_id=route_id,
            input_tokens=10,
            output_tokens=20,
            cost=0,
        )
