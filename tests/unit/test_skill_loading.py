from pathlib import Path

from genesis.skills.loader import FileSystemSkillLoader


def test_skill_discovery_then_progressive_loading(tmp_path: Path) -> None:
    package = tmp_path / "evidence-summary"
    package.mkdir()
    (package / "skill.yaml").write_text(
        """
identity: skill_evidence_summary
version: 1.0.0
purpose: Summarize evidence without changing source meaning.
when_to_use: [When a review needs a concise evidence summary.]
input: {type: object}
output: {type: object}
procedure: Read, trace, summarize, and disclose limitations.
allowed_tools: [tool_source_read]
evidence_requirement: [Every claim references source evidence.]
restrictions: [Do not invent missing evidence.]
failure_modes: [Missing or conflicting evidence.]
escalation: [Return BLOCKED_BY_EVIDENCE.]
evaluation: [All claims are traceable.]
""".strip(),
        encoding="utf-8",
    )
    (package / "SKILL.md").write_text(
        "# Instruksi Skill\n\nBaca evidence dan pertahankan provenance.",
        encoding="utf-8",
    )

    loader = FileSystemSkillLoader()
    descriptors = loader.discover(tmp_path)
    assert len(descriptors) == 1
    assert not hasattr(descriptors[0], "instructions")

    loaded = loader.load(descriptors[0])
    assert "pertahankan provenance" in loaded.instructions
    assert loaded.specification.identity == "skill_evidence_summary"
