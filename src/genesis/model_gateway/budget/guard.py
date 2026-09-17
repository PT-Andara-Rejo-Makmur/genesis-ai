from genesis.model_gateway.types import ModelRequest


class BudgetExceeded(Exception):
    pass


class ExecutionBudgetGuard:
    def validate(self, request: ModelRequest) -> None:
        maximum = request.budget.max_tokens
        if maximum is not None and request.requested_max_tokens > maximum:
            raise BudgetExceeded("Requested tokens exceed the execution budget")
