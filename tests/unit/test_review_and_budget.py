import pytest
from pydantic import ValidationError

from genesis.reviews import AIReviewResult, AIReviewStatus, ReviewType
from genesis.runtime.limits import ExecutionBudget


def test_ai_review_cannot_masquerade_as_authoritative_decision() -> None:
    with pytest.raises(ValidationError):
        AIReviewResult.model_validate(
            {
                "review_id": "review_001",
                "review_type": ReviewType.SECURITY,
                "status": "APPROVED_BY_AI",
                "findings": [],
                "recommendations": [],
            }
        )
    assert "APPROVED_BY_AI" not in {status.value for status in AIReviewStatus}


def test_execution_budget_requires_at_least_one_limit() -> None:
    with pytest.raises(ValidationError):
        ExecutionBudget()


def test_parent_budget_contains_only_bounded_child() -> None:
    parent = ExecutionBudget(max_tokens=1000, max_steps=10)
    assert parent.contains(ExecutionBudget(max_tokens=500, max_steps=5))
    assert not parent.contains(ExecutionBudget(max_tokens=1001, max_steps=5))
