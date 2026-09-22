"""Configuration-only R&D domain semantics for the generic memory selector."""

from genesis.memory.models import MemoryQuery
from genesis.research.models import ResearchDomain

_DOMAIN_HINTS: dict[ResearchDomain, tuple[str, ...]] = {
    ResearchDomain.TECHNOLOGY: ("technology", "teknologi", "software", "platform"),
    ResearchDomain.PROPERTY_BUSINESS: (
        "property business",
        "model bisnis properti",
        "portfolio",
        "investment",
    ),
    ResearchDomain.MANAGEMENT: (
        "management",
        "manajemen perusahaan",
        "organization",
        "governance",
    ),
    ResearchDomain.PROPERTY_MARKET: (
        "property market",
        "pasar properti",
        "demand",
        "pricing",
    ),
}


class ResearchMemoryPolicy:
    """Build domain configuration; all domains use one retrieval service."""

    def query_for(
        self,
        *,
        domain: ResearchDomain,
        goal: str,
        maximum_selected: int = 6,
    ) -> MemoryQuery:
        return MemoryQuery(
            goal=goal,
            requested_domains=(domain,),
            capability_context=_DOMAIN_HINTS[domain],
            require_research_findings=True,
            maximum_selected=maximum_selected,
        )
