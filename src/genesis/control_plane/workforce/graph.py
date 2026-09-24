"""Deterministic capability graph construction."""

from __future__ import annotations

import hashlib

from genesis.control_plane.workforce.models import (
    CapabilityGraph,
    CapabilityNode,
    RequirementUnderstanding,
)


def stable_id(prefix: str, *parts: str) -> str:
    canonical = "\x1f".join(" ".join(part.casefold().split()) for part in parts)
    return f"{prefix}_{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


class CapabilityGraphBuilder:
    def __init__(self, *, max_depth: int = 2) -> None:
        if not 0 <= max_depth <= 8:
            raise ValueError("max_depth must be between 0 and 8")
        self._max_depth = max_depth

    def build(self, understanding: RequirementUnderstanding) -> CapabilityGraph:
        by_identity = {item.identity: item for item in understanding.responsibilities}
        node_ids = {
            identity: stable_id("node", understanding.root_identity, identity)
            for identity in by_identity
        }

        def depth_for(identity: str) -> int:
            seen: set[str] = set()
            depth = 0
            current = by_identity[identity]
            while current.parent_identity is not None and current.parent_identity in by_identity:
                if current.identity in seen:
                    break
                seen.add(current.identity)
                depth += 1
                current = by_identity[current.parent_identity]
            return depth

        nodes = tuple(
            CapabilityNode(
                node_id=node_ids[item.identity],
                capability_identity=item.identity,
                parent_node_id=(
                    node_ids.get(
                        item.parent_identity,
                        stable_id("node", understanding.root_identity, item.parent_identity),
                    )
                    if item.parent_identity is not None
                    else None
                ),
                depth=depth_for(item.identity),
                responsibility=item.purpose,
                atomic=item.atomic,
                input_semantics=item.input_semantics,
                output_semantics=item.output_semantics,
                domain_tags=item.domain_tags,
                required_capability_ids=item.required_capability_ids,
                required_skill_ids=item.required_skill_ids,
                required_tool_ids=item.required_tool_ids,
                permission_refs=item.permission_refs,
                scope_refs=item.scope_refs,
            )
            for item in sorted(
                understanding.responsibilities,
                key=lambda value: (depth_for(value.identity), value.identity),
            )
        )
        return CapabilityGraph(
            root_node_id=node_ids[understanding.root_identity],
            nodes=nodes,
            max_depth=self._max_depth,
        )
