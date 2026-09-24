"""Ports for replaceable workforce intelligence."""

from collections.abc import Sequence
from typing import Protocol

from genesis.control_plane.workforce.models import (
    CapabilityMatch,
    CapabilityNode,
    RequirementUnderstanding,
    WorkforceRegistrySnapshot,
    WorkforceRequirement,
)


class RequirementInterpreter(Protocol):
    async def interpret(self, requirement: WorkforceRequirement) -> RequirementUnderstanding: ...


class CapabilityMatcher(Protocol):
    def match(
        self,
        node: CapabilityNode,
        registry: WorkforceRegistrySnapshot,
        *,
        excluded_capability_ids: Sequence[str] = (),
    ) -> CapabilityMatch: ...
