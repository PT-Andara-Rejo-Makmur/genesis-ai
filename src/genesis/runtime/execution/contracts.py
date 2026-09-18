"""Canonical ToolRequest and ToolResult validation for the GENESIS boundary."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

TOOL_REQUEST_SCHEMA_ID = "https://schemas.alos.dev/v1/tool/tool-request.schema.json"
TOOL_RESULT_SCHEMA_ID = "https://schemas.alos.dev/v1/tool/tool-result.schema.json"


@dataclass(frozen=True, slots=True)
class ToolContractError(Exception):
    contract: str
    path: str
    reason: str


class ToolBoundaryContracts:
    """Load shared contracts without importing Backend or contract source code."""

    def __init__(self, contracts_root: Path) -> None:
        documents: dict[str, dict[str, Any]] = {}
        for pattern in ("schemas/**/*.schema.json", "events/**/*.schema.json"):
            for path in contracts_root.glob(pattern):
                document = json.loads(path.read_text(encoding="utf-8"))
                schema_id = document.get("$id")
                if schema_id:
                    documents[str(schema_id)] = document
        required = {TOOL_REQUEST_SCHEMA_ID, TOOL_RESULT_SCHEMA_ID}
        if not required.issubset(documents):
            raise ValueError("Canonical ToolRequest/ToolResult schemas were not found")
        registry = Registry().with_resources(
            (schema_id, Resource.from_contents(schema)) for schema_id, schema in documents.items()
        )
        self._request = Draft202012Validator(
            documents[TOOL_REQUEST_SCHEMA_ID], registry=registry, format_checker=FormatChecker()
        )
        self._result = Draft202012Validator(
            documents[TOOL_RESULT_SCHEMA_ID], registry=registry, format_checker=FormatChecker()
        )

    @staticmethod
    def _validate(
        validator: Draft202012Validator,
        payload: Mapping[str, Any],
        contract: str,
    ) -> None:
        errors = sorted(validator.iter_errors(dict(payload)), key=lambda item: list(item.path))
        if errors:
            first = errors[0]
            path = ".".join(str(part) for part in first.path) or "$"
            raise ToolContractError(contract=contract, path=path, reason=first.message)

    def validate_request(self, payload: Mapping[str, Any]) -> None:
        self._validate(self._request, payload, "ToolRequest")

    def validate_result(self, payload: Mapping[str, Any]) -> None:
        self._validate(self._result, payload, "ToolResult")
