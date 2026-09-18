"""Immutable prompt-version metadata; model providers are accessed only via ModelGateway."""

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptTemplateVersion:
    prompt_id: str
    version: str
    template: str
    sha256: str

    def render(self, **values: str) -> str:
        try:
            return self.template.format_map(values)
        except KeyError as exc:
            raise ValueError(f"prompt value is missing: {exc.args[0]}") from exc


def version_prompt(*, prompt_id: str, version: str, template: str) -> PromptTemplateVersion:
    if not prompt_id or not version or not template.strip():
        raise ValueError("prompt id, version, and template are required")
    digest = hashlib.sha256(template.encode("utf-8")).hexdigest()
    return PromptTemplateVersion(
        prompt_id=prompt_id,
        version=version,
        template=template,
        sha256=digest,
    )
