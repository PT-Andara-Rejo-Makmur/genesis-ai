from genesis.model_gateway.types import ModelRequest, ModelResponse


class BudgetExceeded(Exception):
    def __init__(self, message: str, *, response: ModelResponse | None = None) -> None:
        super().__init__(message)
        self.response = response


class ExecutionBudgetGuard:
    def validate(self, request: ModelRequest) -> None:
        maximum = request.budget.max_tokens
        if maximum is None:
            raise BudgetExceeded("A finite token budget is required for model inference")
        if maximum is not None and request.requested_max_tokens > maximum:
            raise BudgetExceeded("Requested tokens exceed the execution budget")
