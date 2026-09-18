from genesis.research import ResearchDomain
from genesis.research.domains import DOMAIN_TAXONOMY, SHARED_RESEARCH_ENGINE_ID


def test_four_rd_domains_are_complete_and_share_one_engine() -> None:
    assert set(DOMAIN_TAXONOMY) == set(ResearchDomain)
    assert {profile.display_name for profile in DOMAIN_TAXONOMY.values()} == {
        "Teknologi",
        "Model Bisnis Properti",
        "Manajemen Perusahaan",
        "Properti",
    }
    assert {profile.engine_id for profile in DOMAIN_TAXONOMY.values()} == {
        SHARED_RESEARCH_ENGINE_ID
    }


def test_every_rd_domain_defines_boundary_evidence_and_allowed_outputs() -> None:
    for profile in DOMAIN_TAXONOMY.values():
        assert profile.purpose
        assert profile.scope_boundary
        assert profile.expected_evidence
        assert profile.allowed_findings
        assert profile.allowed_recommendations
