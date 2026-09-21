"""Research Skill references mapped to the existing ResearchDomain taxonomy."""

from genesis.research import ResearchDomain
from genesis.research.domains import SHARED_RESEARCH_ENGINE_ID
from genesis.skills.loader import SkillReference

CORE_RESEARCH_SKILL_REF = SkillReference(skill_id="skill.research.core", skill_version="1.0.0")

RESEARCH_SKILL_REFS: dict[ResearchDomain, SkillReference] = {
    ResearchDomain.TECHNOLOGY: SkillReference(
        skill_id="skill.research.technology", skill_version="1.0.0"
    ),
    ResearchDomain.PROPERTY_BUSINESS: SkillReference(
        skill_id="skill.research.property_business", skill_version="1.0.0"
    ),
    ResearchDomain.MANAGEMENT: SkillReference(
        skill_id="skill.research.management", skill_version="1.0.0"
    ),
    ResearchDomain.PROPERTY_MARKET: SkillReference(
        skill_id="skill.research.property_market", skill_version="1.0.0"
    ),
}


def research_skill_ref(domain: ResearchDomain) -> SkillReference:
    return RESEARCH_SKILL_REFS[domain]


__all__ = [
    "CORE_RESEARCH_SKILL_REF",
    "RESEARCH_SKILL_REFS",
    "SHARED_RESEARCH_ENGINE_ID",
    "research_skill_ref",
]
