"""Deterministic bounded context selection."""

from __future__ import annotations

from collections.abc import Sequence

from genesis.runtime.context.models import (
    ContextFailure,
    ContextSegment,
    ContextSelection,
    ContextSelectionMetadata,
)


class ContextBudgetManager:
    def select(
        self,
        segments: Sequence[ContextSegment],
        *,
        maximum_characters: int,
        correlation_id: str,
    ) -> ContextSelection:
        if maximum_characters < 1:
            raise ContextFailure(
                "CONTEXT_BUDGET_INVALID",
                "Context character budget must be positive.",
                correlation_id,
            )
        ordered = sorted(segments, key=lambda item: (int(item.priority), item.segment_id))
        required_size = sum(item.size_characters for item in ordered if item.required)
        if required_size > maximum_characters:
            raise ContextFailure(
                "CONTEXT_BUDGET_REQUIRED_OVERFLOW",
                "Required authority, goal, business context, and evidence exceed the budget.",
                correlation_id,
                details={
                    "required_characters": required_size,
                    "maximum_characters": maximum_characters,
                },
            )

        selected: list[ContextSegment] = []
        dropped: list[ContextSegment] = []
        reasons: dict[str, str] = {}
        used = 0
        for item in ordered:
            if item.required or used + item.size_characters <= maximum_characters:
                selected.append(item)
                used += item.size_characters
                reasons[item.segment_id] = "SELECTED_BY_PRIORITY"
            else:
                dropped.append(item)
                reasons[item.segment_id] = "DROPPED_CONTEXT_BUDGET"
        return ContextSelection(
            selected=tuple(selected),
            dropped=tuple(dropped),
            metadata=ContextSelectionMetadata(
                maximum_characters=maximum_characters,
                selected_characters=used,
                selected_segment_ids=tuple(item.segment_id for item in selected),
                dropped_segment_ids=tuple(item.segment_id for item in dropped),
                reason_by_segment=reasons,
            ),
        )
