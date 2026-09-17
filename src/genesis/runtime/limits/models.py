from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExecutionBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_tokens: int | None = Field(default=None, ge=1)
    max_cost: float | None = Field(default=None, ge=0)
    max_steps: int | None = Field(default=None, ge=1)
    max_tool_calls: int | None = Field(default=None, ge=0)
    max_children: int | None = Field(default=None, ge=0)
    max_depth: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, ge=1)
    concurrency_limit: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_at_least_one_limit(self) -> ExecutionBudget:
        if all(value is None for value in self.model_dump().values()):
            raise ValueError("At least one execution budget limit is required")
        return self

    def contains(self, child: ExecutionBudget) -> bool:
        for field_name in type(self).model_fields:
            parent_value = getattr(self, field_name)
            child_value = getattr(child, field_name)
            if parent_value is not None and (child_value is None or child_value > parent_value):
                return False
        return True
