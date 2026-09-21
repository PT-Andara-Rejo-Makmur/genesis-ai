from pathlib import Path

import pytest

from genesis.contracts import CanonicalContractCatalog
from genesis.skills.loader import FileSystemSkillLoader, SkillFailureCode, SkillPackageError

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


def manifest(*, extra: str = "") -> str:
    return f"""
skill_id: skill.evidence.summary
skill_version: 1.0.0
name: Evidence Summary
description: Summarize evidence without changing source meaning.
purpose: Summarize evidence without changing source meaning.
when_to_use: [A review needs a concise evidence summary.]
input_schema_ref: https://schemas.alos.dev/v1/research/research-request.schema.json
output_schema_ref: https://schemas.alos.dev/v1/research/research-result.schema.json
procedure: [Read evidence., Trace claims., Summarize and disclose limitations.]
required_tool_ids: [source.search_context]
evidence_requirements: [Every claim references source evidence.]
restrictions: [Do not invent missing evidence.]
failure_modes: [Missing or conflicting evidence.]
escalation: [Return an explicit insufficient-evidence limitation.]
evaluation: [All claims are traceable.]
{extra}
""".strip()


def loader() -> FileSystemSkillLoader:
    return FileSystemSkillLoader(contracts=CanonicalContractCatalog(CONTRACTS_ROOT))


def test_skill_discovery_then_progressive_loading(tmp_path: Path) -> None:
    package = tmp_path / "evidence-summary"
    package.mkdir()
    (package / "skill.yaml").write_text(manifest(), encoding="utf-8")
    (package / "SKILL.md").write_text(
        "# Skill instructions\n\nPreserve provenance.", encoding="utf-8"
    )

    descriptors = loader().discover(tmp_path)
    assert len(descriptors) == 1
    assert not hasattr(descriptors[0], "instructions")

    loaded = loader().load(descriptors[0])
    assert "Preserve provenance" in loaded.instructions
    assert loaded.specification.skill_id == "skill.evidence.summary"


def test_noncanonical_or_extra_manifest_fields_fail_closed(tmp_path: Path) -> None:
    package = tmp_path / "bad"
    package.mkdir()
    (package / "skill.yaml").write_text(
        manifest(extra="authority: SELF_APPROVED"), encoding="utf-8"
    )

    with pytest.raises(SkillPackageError) as raised:
        loader().discover(tmp_path)

    assert raised.value.code is SkillFailureCode.INVALID_MANIFEST


def test_missing_skill_markdown_fails_explicitly(tmp_path: Path) -> None:
    package = tmp_path / "missing-instructions"
    package.mkdir()
    (package / "skill.yaml").write_text(manifest(), encoding="utf-8")
    descriptor = loader().discover(tmp_path)[0]

    with pytest.raises(SkillPackageError) as raised:
        loader().load(descriptor)

    assert raised.value.code is SkillFailureCode.MISSING_INSTRUCTIONS


def test_deprecated_tool_ids_are_accepted_but_ignored(tmp_path: Path) -> None:
    package = tmp_path / "legacy"
    package.mkdir()
    (package / "skill.yaml").write_text(
        manifest(extra="tool_ids: [tool.must.not.grant]"), encoding="utf-8"
    )
    (package / "SKILL.md").write_text("# Safe instructions", encoding="utf-8")
    specification = loader().discover(tmp_path)[0].specification
    assert specification.required_tool_ids == ("source.search_context",)
    assert not hasattr(specification, "tool_ids")


def test_canonical_governance_metadata_is_deprojected_from_runtime(tmp_path: Path) -> None:
    package = tmp_path / "governed"
    package.mkdir()
    (package / "skill.yaml").write_text(
        manifest(extra="owner_actor_id: actor_skill_owner\nrisk_level: HIGH"),
        encoding="utf-8",
    )
    (package / "SKILL.md").write_text("# Safe instructions", encoding="utf-8")

    specification = loader().discover(tmp_path)[0].specification

    assert specification.skill_id == "skill.evidence.summary"
    assert not hasattr(specification, "owner_actor_id")
    assert not hasattr(specification, "risk_level")


def test_skill_package_rejects_executable_files(tmp_path: Path) -> None:
    package = tmp_path / "unsafe"
    package.mkdir()
    (package / "skill.yaml").write_text(manifest(), encoding="utf-8")
    (package / "SKILL.md").write_text("# Safe instructions", encoding="utf-8")
    (package / "payload.py").write_text("raise RuntimeError()", encoding="utf-8")
    descriptor = loader().discover(tmp_path)[0]
    with pytest.raises(SkillPackageError) as raised:
        loader().load(descriptor)
    assert raised.value.code is SkillFailureCode.INVALID_MANIFEST
