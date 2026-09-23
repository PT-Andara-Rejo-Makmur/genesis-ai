from pathlib import Path

from genesis.contracts import CanonicalContractCatalog
from genesis.research import ResearchDomain
from genesis.research.domains import DOMAIN_TAXONOMY, SHARED_RESEARCH_ENGINE_ID
from genesis.skills.loader import FileSystemSkillLoader

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_ROOT = ROOT.parent / "alos-contracts"
RESEARCH_SKILLS = ROOT / "blueprints" / "skills" / "research"
DOMAIN_IDS = {
    "skill.research.technology",
    "skill.research.property_business",
    "skill.research.management",
    "skill.research.property_market",
}


def descriptors():  # type: ignore[no-untyped-def]
    loader = FileSystemSkillLoader(contracts=CanonicalContractCatalog(CONTRACTS_ROOT))
    return loader, loader.discover(RESEARCH_SKILLS)


def test_generic_and_exactly_four_domain_research_packages_are_canonical() -> None:
    _, discovered = descriptors()
    ids = {item.specification.skill_id for item in discovered}

    assert ids == {"skill.research.core", *DOMAIN_IDS}
    domain_ids = {
        item.specification.skill_id for item in discovered if item.package_path.name != "core"
    }
    assert domain_ids == DOMAIN_IDS
    assert all(
        item.specification.input_schema_ref.endswith("research-request.schema.json")
        for item in discovered
    )
    assert all(
        item.specification.output_schema_ref.endswith("research-result.schema.json")
        for item in discovered
    )
    assert all((item.package_path / "SKILL.md").is_file() for item in discovered)


def test_research_skill_procedure_is_governed_and_does_not_guess() -> None:
    loader, discovered = descriptors()
    core = next(item for item in discovered if item.specification.skill_id == "skill.research.core")
    text = loader.load(core).instructions.lower()

    assert "researchdecision" in text
    assert "backend `toolexecutor`" in text
    assert "data tidak tepercaya" in text
    assert "jangan menebak" in text
    assert "non-otoritatif" in text
    assert "claim-to-evidence map" in text
    assert "kondisi berhenti" in text
    assert "checklist evaluasi" in text
    assert len(text) > 8_000


def test_each_domain_has_specific_source_evidence_conflict_and_forbidden_action_guidance() -> None:
    loader, discovered = descriptors()
    for descriptor in discovered:
        if descriptor.specification.skill_id == "skill.research.core":
            continue
        text = loader.load(descriptor).instructions.lower()
        assert "input minimum" in text
        assert "prosedur domain" in text
        assert "evidence" in text
        assert "penanganan konflik" in text
        assert "format keluaran domain" in text
        assert "larangan tindakan otomatis" in text
        assert "checklist evaluasi" in text
        assert "jangan" in text
        assert len(text) > 5_000


def test_manifest_content_uses_indonesian_while_preserving_canonical_fields() -> None:
    _, discovered = descriptors()
    for descriptor in discovered:
        specification = descriptor.specification
        assert specification.name.startswith("Riset")
        assert specification.purpose
        assert specification.when_to_use
        assert specification.procedure
        assert specification.evidence_requirements
        assert specification.restrictions
        assert specification.failure_modes
        assert specification.escalation
        assert specification.evaluation


def test_domain_packages_map_to_existing_taxonomy_and_one_engine() -> None:
    assert set(DOMAIN_TAXONOMY) == set(ResearchDomain)
    assert {profile.engine_id for profile in DOMAIN_TAXONOMY.values()} == {
        SHARED_RESEARCH_ENGINE_ID
    }
