"""Shared finite token-budget semantics for the bounded research model pipeline."""

from genesis.research.orchestration.models import ModelCallUsage
from genesis.runtime.limits import ExecutionBudget

DEFAULT_RESEARCH_MODEL_TOKEN_BUDGET = 4_000


def effective_model_token_limit(budget: ExecutionBudget) -> int:
    """Return the canonical token limit or the finite local research default."""

    return (
        budget.max_tokens if budget.max_tokens is not None else DEFAULT_RESEARCH_MODEL_TOKEN_BUDGET
    )


def remaining_model_tokens(
    budget: ExecutionBudget,
    prior_usage: ModelCallUsage,
) -> int:
    """Return cumulative remaining research model tokens without resetting usage."""

    return max(0, effective_model_token_limit(budget) - prior_usage.total_tokens)
