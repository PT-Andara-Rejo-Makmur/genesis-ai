"""R&D domain profiles sharing the single GENESIS research engine."""

from pydantic import BaseModel, ConfigDict, Field

from genesis.research.models import ResearchDomain

SHARED_RESEARCH_ENGINE_ID = "genesis.research.engine.v1"


class ResearchDomainProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    domain: ResearchDomain
    display_name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    scope_boundary: tuple[str, ...] = Field(min_length=1)
    expected_evidence: tuple[str, ...] = Field(min_length=1)
    allowed_findings: tuple[str, ...] = Field(min_length=1)
    allowed_recommendations: tuple[str, ...] = Field(min_length=1)
    engine_id: str = SHARED_RESEARCH_ENGINE_ID


DOMAIN_TAXONOMY: dict[ResearchDomain, ResearchDomainProfile] = {
    ResearchDomain.TECHNOLOGY: ResearchDomainProfile(
        domain=ResearchDomain.TECHNOLOGY,
        display_name="Teknologi",
        purpose="Evaluate technologies, models, frameworks, tools, and architecture options.",
        scope_boundary=(
            "Technical fitness, security, interoperability, cost, and maintainability.",
            "No automatic ModelGateway, infrastructure, or production configuration change.",
        ),
        expected_evidence=(
            "Versioned vendor or project documentation.",
            "Reproducible benchmark, evaluation, or compatibility evidence.",
            "Security, operational, and cost constraints.",
        ),
        allowed_findings=("Capability gap.", "Compatibility or security risk.", "Trade-off."),
        allowed_recommendations=(
            "Evaluation or proof-of-concept proposal.",
            "Governed adoption, upgrade, or rejection recommendation.",
        ),
    ),
    ResearchDomain.PROPERTY_BUSINESS: ResearchDomainProfile(
        domain=ResearchDomain.PROPERTY_BUSINESS,
        display_name="Model Bisnis Properti",
        purpose="Evaluate property business models, packages, pricing, and unit economics.",
        scope_boundary=(
            "Commercial assumptions, scenarios, value proposition, revenue, and cost model.",
            "No pricing, contract, budget, or commercial decision becomes authoritative.",
        ),
        expected_evidence=(
            "Traceable financial and operating assumptions.",
            "Comparable market or internal performance evidence.",
            "Scenario sensitivity and limitations.",
        ),
        allowed_findings=("Business-model opportunity.", "Unit-economics risk.", "Assumption gap."),
        allowed_recommendations=(
            "Scenario or experiment proposal.",
            "Pricing or package recommendation requiring domain review.",
        ),
    ),
    ResearchDomain.MANAGEMENT: ResearchDomainProfile(
        domain=ResearchDomain.MANAGEMENT,
        display_name="Manajemen Perusahaan",
        purpose="Evaluate company processes, governance, SOPs, organization, and KPIs.",
        scope_boundary=(
            "Process, control, accountability, capacity, and management benchmark.",
            "No automatic policy, role, KPI, permission, or organizational change.",
        ),
        expected_evidence=(
            "Approved internal policy, SOP, and performance evidence.",
            "Applicable governance or management benchmark.",
            "Stakeholder and implementation constraints.",
        ),
        allowed_findings=("Process gap.", "Control or governance risk.", "KPI ambiguity."),
        allowed_recommendations=(
            "Draft SOP, control, or KPI improvement.",
            "Human-reviewed operating-model recommendation.",
        ),
    ),
    ResearchDomain.PROPERTY_MARKET: ResearchDomainProfile(
        domain=ResearchDomain.PROPERTY_MARKET,
        display_name="Properti",
        purpose="Evaluate property markets, regions, competitors, regulation, and social trends.",
        scope_boundary=(
            "Market, asset, location, competitor, demand, regulation, and trend analysis.",
            "No acquisition, sale, investment, legal, or regulatory decision is executed.",
        ),
        expected_evidence=(
            "Fresh, cited market or transaction evidence.",
            "Approved regulatory or official source where applicable.",
            "Region, time period, method, reliability, and limitations.",
        ),
        allowed_findings=("Market signal.", "Property risk.", "Regulatory or evidence gap."),
        allowed_recommendations=(
            "Further due-diligence proposal.",
            "Human-reviewed market or property strategy recommendation.",
        ),
    ),
}


def domain_profile(domain: ResearchDomain) -> ResearchDomainProfile:
    return DOMAIN_TAXONOMY[domain]
