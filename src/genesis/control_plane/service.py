from dataclasses import dataclass

from genesis.agents.definitions import AgentDraft


@dataclass(frozen=True, slots=True)
class WorkforceAssessment:
    draft_id: str
    ready_for_backend_review: bool
    findings: tuple[str, ...]


class WorkforceControlPlane:
    """Assesses workforce artifacts but never activates or approves them."""

    def assess_agent_draft(self, draft: AgentDraft) -> WorkforceAssessment:
        findings: list[str] = []
        if not draft.definition.scope_refs:
            findings.append("Agent definition requires at least one scope")
        if draft.status != "SUBMITTED_FOR_REVIEW":
            findings.append("Agent draft has not been submitted for review")
        return WorkforceAssessment(
            draft_id=draft.draft_id,
            ready_for_backend_review=not findings,
            findings=tuple(findings),
        )
