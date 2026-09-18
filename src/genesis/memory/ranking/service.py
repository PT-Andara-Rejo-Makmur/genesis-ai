"""Deterministic evidence-preserving ranking for already-authorized context."""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
from typing import Any


class EvidenceAwareRanker:
    """Ranks ContextBundle items without expanding scope or fetching persistence."""

    def rank(
        self,
        context_bundle: Mapping[str, Any],
        *,
        query: str,
        max_items: int = 12,
    ) -> dict[str, Any]:
        if not 1 <= max_items <= 50:
            raise ValueError("max_items must be between 1 and 50")
        terms = set(re.findall(r"[a-z0-9_]+", query.casefold()))
        items = context_bundle.get("items")
        if not isinstance(items, list):
            raise ValueError("ContextBundle items must be an array")
        scored: list[tuple[int, int, Mapping[str, Any]]] = []
        for index, item in enumerate(items):
            if not isinstance(item, Mapping):
                raise ValueError("ContextBundle item must be an object")
            searchable = json.dumps(item.get("value"), sort_keys=True).casefold()
            score = sum(term in searchable for term in terms)
            scored.append((score, index, item))
        scored.sort(key=lambda value: (-value[0], value[1]))
        selected = [copy.deepcopy(dict(item)) for _score, _index, item in scored[:max_items]]
        selected_evidence = {str(item["evidence_id"]) for item in selected}
        evidence_refs = context_bundle.get("evidence_refs", [])
        filtered_refs = [
            copy.deepcopy(dict(ref))
            for ref in evidence_refs
            if isinstance(ref, Mapping) and str(ref.get("evidence_id")) in selected_evidence
        ]
        ranked = copy.deepcopy(dict(context_bundle))
        ranked["items"] = selected
        ranked["evidence_refs"] = filtered_refs
        return ranked
