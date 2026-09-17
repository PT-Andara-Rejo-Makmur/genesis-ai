from genesis.evals import EvaluationTaxonomy, RiskBasedTestProfile


def test_risk_profile_selects_relevant_taxonomies_only() -> None:
    profile = RiskBasedTestProfile(
        profile_id="eval_profile_readonly_001",
        capability_id="cap_research_readonly",
        risk_level="MEDIUM",
        required_taxonomies=frozenset({EvaluationTaxonomy.POSITIVE, EvaluationTaxonomy.SECURITY}),
        rationale="Read-only research needs expected behavior and authority-boundary tests.",
    )
    assert EvaluationTaxonomy.RECOVERY not in profile.required_taxonomies
    assert len(profile.required_taxonomies) == 2
