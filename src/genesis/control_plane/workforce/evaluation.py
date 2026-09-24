"""Structured evaluation requirement planning; results never grant approval."""

from genesis.control_plane.workforce.graph import stable_id
from genesis.control_plane.workforce.models import (
    CapabilityNode,
    EvaluationKind,
    EvaluationRequirement,
)

_OBJECTIVES: dict[EvaluationKind, tuple[str, tuple[str, ...]]] = {
    EvaluationKind.FUNCTIONAL: (
        "Verify the responsibility produces its declared output for valid input.",
        ("schema-valid output", "functional assertions"),
    ),
    EvaluationKind.PERMISSION_SCOPE: (
        "Verify execution fails closed outside supplied permission and scope bounds.",
        ("authorization decision", "scope and permission observations"),
    ),
    EvaluationKind.TOOL_BEHAVIOR: (
        "Verify tool requests use Backend ToolExecutor and handle unavailable tools safely.",
        ("ToolRequest/ToolResult evidence", "safe failure observation"),
    ),
    EvaluationKind.EVIDENCE: (
        "Verify material conclusions retain immutable evidence lineage.",
        ("evidence references", "lineage assertions"),
    ),
    EvaluationKind.BUDGET: (
        "Verify model, tool, and delegation work remains within the supplied budget.",
        ("usage observation", "budget assertion"),
    ),
    EvaluationKind.DELEGATION: (
        "Verify child work preserves lineage and cannot expand parent authority.",
        ("delegation lineage", "authority subset assertion"),
    ),
    EvaluationKind.SAFE_FAILURE: (
        "Verify dependency and runtime failures are bounded, explicit, and non-authoritative.",
        ("failure code", "no fabricated-success assertion"),
    ),
    EvaluationKind.DUPLICATION: (
        "Verify no duplicate capability or responsibility is planned.",
        ("identity census", "duplicate assertion"),
    ),
    EvaluationKind.REGRESSION: (
        "Verify existing governed behavior and contracts remain unchanged.",
        ("regression suite result", "contract validation"),
    ),
}


class EvaluationPlanner:
    def plan(self, node: CapabilityNode) -> tuple[EvaluationRequirement, ...]:
        return tuple(
            EvaluationRequirement(
                evaluation_id=stable_id("eval", node.node_id, kind.value),
                kind=kind,
                objective=objective,
                expected_evidence=evidence,
            )
            for kind, (objective, evidence) in _OBJECTIVES.items()
        )

