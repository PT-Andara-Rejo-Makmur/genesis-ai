"""Generic deterministic interpretation behind a future ModelGateway adapter."""

from __future__ import annotations

import re

from genesis.control_plane.workforce.models import (
    RequirementUnderstanding,
    ResponsibilityCandidate,
    ResponsibilityRequirement,
    WorkforceRequirement,
)

_DECOMPOSITION_INTRODUCTION = re.compile(
    r"\b(?:across|through|via|melalui|dengan area|mencakup area)\b\s*:?",
    re.IGNORECASE,
)
_NESTING_MARKER = re.compile(
    r"\b(?:including|includes|covering|covers|comprising|termasuk|mencakup)\b\s*:?",
    re.IGNORECASE,
)
_LEADING_ACTIONS = {
    "analyze",
    "build",
    "coordinate",
    "create",
    "kelola",
    "koordinasikan",
    "manage",
    "monitor",
    "orchestrate",
    "oversee",
    "plan",
    "rancang",
}
_IDENTITY_STOPWORDS = {
    "a",
    "an",
    "and",
    "dan",
    "for",
    "of",
    "the",
    "untuk",
    "with",
    "yang",
}


class DeterministicRequirementInterpreter:
    """Extract objective and generic responsibility expressions without domain knowledge."""

    async def interpret(self, requirement: WorkforceRequirement) -> RequirementUnderstanding:
        normalized = " ".join(requirement.requirement.statement.casefold().split())
        if requirement.responsibility_hints:
            candidates = self._from_hints(requirement)
            root_identity = self._root_identity(candidates)
            root_purpose = next(
                item.purpose for item in candidates if item.identity == root_identity
            )
            rationale: tuple[str, ...] = (
                "Interpreted caller-supplied structured responsibility semantics.",
            )
        else:
            root_phrase, body = self._objective_and_body(normalized)
            root_identity = self._identity(root_phrase)
            candidates = self._from_generic_syntax(requirement, root_identity, body)
            root_purpose = requirement.requirement.statement.strip()
            rationale = (
                "Extracted objective, responsibility lists, and nested clauses using generic "
                "deterministic syntax.",
                "Atomicity, parent assignment, and bounded hierarchy remain decomposition "
                "decisions.",
            )
        return RequirementUnderstanding(
            normalized_requirement=normalized,
            root_identity=root_identity,
            root_purpose=root_purpose,
            candidates=candidates,
            rationale=rationale,
        )

    def _from_hints(
        self, requirement: WorkforceRequirement
    ) -> tuple[ResponsibilityCandidate, ...]:
        context = requirement.requirement.execution_context
        child_map: dict[str, list[str]] = {}
        for hint in requirement.responsibility_hints:
            if hint.parent_identity is not None:
                child_map.setdefault(hint.parent_identity, []).append(hint.identity)
        return tuple(
            self._candidate_from_hint(
                hint,
                tuple(sorted(set(child_map.get(hint.identity, ())))),
                context.permission_refs,
                context.scope_refs,
            )
            for hint in sorted(requirement.responsibility_hints, key=lambda item: item.identity)
        )

    @staticmethod
    def _candidate_from_hint(
        hint: ResponsibilityRequirement,
        child_identities: tuple[str, ...],
        inherited_permissions: tuple[str, ...],
        inherited_scopes: tuple[str, ...],
    ) -> ResponsibilityCandidate:
        return ResponsibilityCandidate(
            identity=hint.identity,
            purpose=hint.purpose,
            parent_hint=hint.parent_identity,
            child_identities=child_identities,
            input_semantics=tuple(sorted(set(hint.input_semantics))),
            output_semantics=tuple(sorted(set(hint.output_semantics))),
            domain_tags=tuple(sorted(set(hint.domain_tags))),
            required_capability_ids=tuple(sorted(set(hint.required_capability_ids))),
            required_skill_ids=tuple(sorted(set(hint.required_skill_ids))),
            required_tool_ids=tuple(sorted(set(hint.required_tool_ids))),
            permission_refs=tuple(
                sorted(
                    set(
                        inherited_permissions
                        if hint.permission_refs is None
                        else hint.permission_refs
                    )
                )
            ),
            scope_refs=tuple(
                sorted(set(inherited_scopes if hint.scope_refs is None else hint.scope_refs))
            ),
        )

    def _from_generic_syntax(
        self,
        requirement: WorkforceRequirement,
        root_identity: str,
        body: str,
    ) -> tuple[ResponsibilityCandidate, ...]:
        context = requirement.requirement.execution_context
        parsed: list[ResponsibilityCandidate] = []
        top_level_ids: list[str] = []
        segments = self._top_level_segments(body)
        for segment in segments:
            nesting = _NESTING_MARKER.search(segment)
            if nesting is None:
                for phrase in self._list_items(segment):
                    candidate = self._generic_candidate(
                        phrase,
                        permission_refs=context.permission_refs,
                        scope_refs=context.scope_refs,
                    )
                    parsed.append(candidate)
                    top_level_ids.append(candidate.identity)
                continue
            parent_phrase = segment[: nesting.start()].strip(" ,:-")
            child_phrases = self._list_items(segment[nesting.end() :])
            parent_identity = self._identity(parent_phrase)
            child_ids = tuple(self._identity(phrase) for phrase in child_phrases)
            parsed.append(
                self._generic_candidate(
                    parent_phrase,
                    child_identities=child_ids,
                    permission_refs=context.permission_refs,
                    scope_refs=context.scope_refs,
                )
            )
            top_level_ids.append(parent_identity)
            parsed.extend(
                self._generic_candidate(
                    phrase,
                    parent_hint=parent_identity,
                    permission_refs=context.permission_refs,
                    scope_refs=context.scope_refs,
                )
                for phrase in child_phrases
            )

        merged = self._merge_candidates(parsed)
        root = ResponsibilityCandidate(
            identity=root_identity,
            purpose=requirement.requirement.statement.strip(),
            child_identities=tuple(sorted(set(top_level_ids))),
            input_semantics=("business requirement",),
            output_semantics=("reviewable workforce result",),
            required_capability_ids=tuple(sorted(set(requirement.required_capability_ids))),
            required_skill_ids=tuple(sorted(set(requirement.required_skill_ids))),
            required_tool_ids=tuple(sorted(set(requirement.required_tool_ids))),
            permission_refs=tuple(sorted(set(context.permission_refs))),
            scope_refs=tuple(sorted(set(context.scope_refs))),
        )
        return (root, *merged)

    @staticmethod
    def _objective_and_body(normalized: str) -> tuple[str, str]:
        introduction = _DECOMPOSITION_INTRODUCTION.search(normalized)
        if introduction is None:
            return DeterministicRequirementInterpreter._strip_leading_action(normalized), ""
        objective = DeterministicRequirementInterpreter._strip_leading_action(
            normalized[: introduction.start()]
        )
        return objective, normalized[introduction.end() :].strip(" .")

    @staticmethod
    def _strip_leading_action(value: str) -> str:
        tokens = re.findall(r"[a-z0-9]+", value.casefold())
        while tokens and tokens[0] in _LEADING_ACTIONS | {"a", "an", "the", "to"}:
            tokens.pop(0)
        return " ".join(tokens) or "general requirement"

    @staticmethod
    def _top_level_segments(body: str) -> tuple[str, ...]:
        if not body:
            return ()
        values: list[str] | tuple[str, ...]
        if ";" in body:
            values = body.split(";")
        elif _NESTING_MARKER.search(body):
            values = (body,)
        else:
            values = re.split(r",|\band\b|\bdan\b|\bserta\b", body)
        return tuple(value.strip(" .,:-") for value in values if value.strip(" .,:-"))

    @staticmethod
    def _list_items(value: str) -> tuple[str, ...]:
        parts = re.split(r",|\band\b|\bdan\b|\bserta\b", value)
        return tuple(
            re.sub(r"^(?:and|dan|serta)\s+", "", part.strip(" .,:-"))
            for part in parts
            if part.strip(" .,:-")
        )

    @classmethod
    def _generic_candidate(
        cls,
        phrase: str,
        *,
        parent_hint: str | None = None,
        child_identities: tuple[str, ...] = (),
        permission_refs: tuple[str, ...],
        scope_refs: tuple[str, ...],
    ) -> ResponsibilityCandidate:
        identity = cls._identity(phrase)
        return ResponsibilityCandidate(
            identity=identity,
            purpose=f"Handle the bounded responsibility: {phrase.strip()}.",
            parent_hint=parent_hint,
            child_identities=tuple(sorted(set(child_identities))),
            input_semantics=(f"{identity} input",),
            output_semantics=(f"{identity} result",),
            permission_refs=tuple(sorted(set(permission_refs))),
            scope_refs=tuple(sorted(set(scope_refs))),
        )

    @staticmethod
    def _merge_candidates(
        candidates: list[ResponsibilityCandidate],
    ) -> tuple[ResponsibilityCandidate, ...]:
        merged: dict[str, ResponsibilityCandidate] = {}
        for candidate in candidates:
            existing = merged.get(candidate.identity)
            if existing is None:
                merged[candidate.identity] = candidate
                continue
            merged[candidate.identity] = existing.model_copy(
                update={
                    "parent_hint": existing.parent_hint or candidate.parent_hint,
                    "child_identities": tuple(
                        sorted(set(existing.child_identities) | set(candidate.child_identities))
                    ),
                }
            )
        return tuple(merged[key] for key in sorted(merged))

    @staticmethod
    def _root_identity(candidates: tuple[ResponsibilityCandidate, ...]) -> str:
        roots = tuple(item.identity for item in candidates if item.parent_hint is None)
        choices = roots or tuple(item.identity for item in candidates)
        return sorted(choices)[0]

    @staticmethod
    def _identity(value: str) -> str:
        tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", value.casefold())
            if token not in _IDENTITY_STOPWORDS
        ]
        identity = ".".join(tokens) or "general.requirement"
        return identity[:128]
