"""Present canonical values honestly and omit operational authority from model context."""

from typing import Any

_AUTHORITY_FIELDS = frozenset(
    {
        "instruction_authority",
        "tenant_id",
        "organization_id",
        "workspace_id",
        "actor_id",
        "permission_refs",
        "scope_refs",
        "allowed_tool_ids",
        "execution_budget",
        "authority_context",
    }
)


def data_only(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: data_only(item) for key, item in value.items() if key not in _AUTHORITY_FIELDS}
    if isinstance(value, list):
        return [data_only(item) for item in value]
    return value


def display(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Ya" if value else "Tidak"
    if isinstance(value, dict):
        return "\n".join(
            f"{key.replace('_', ' ')}: {display(item)}"
            for key, item in value.items()
            if key not in _AUTHORITY_FIELDS
        )
    if isinstance(value, list):
        return "Belum ada data" if not value else "\n\n".join(display(item) for item in value[:20])
    return {"UNAVAILABLE": "Belum Terhubung", "NOT_CONNECTED": "Belum Terhubung"}.get(
        str(value), str(value)
    )
