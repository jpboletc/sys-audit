"""Skills registry and management."""

from sys_audit.skills.base import BaseSkill

# Registry of available skills
_skills: dict[str, BaseSkill] = {}


def register_skill(skill: BaseSkill) -> None:
    """Register a skill in the global registry."""
    _skills[skill.name] = skill


def get_available_skills() -> list[BaseSkill]:
    """Get all registered skills."""
    _load_builtin_skills()
    return list(_skills.values())


def get_skill_by_name(name: str) -> BaseSkill | None:
    """Get a skill by name."""
    _load_builtin_skills()
    return _skills.get(name)


def validate_skill(skill: BaseSkill) -> list[str]:
    """Validate a skill configuration.

    Returns:
        List of validation issues (empty if valid)
    """
    issues = []

    if not skill.name:
        issues.append("Skill has no name")
    if not skill.version:
        issues.append("Skill has no version")
    if not skill.description:
        issues.append("Skill has no description")
    if not skill.stakeholders:
        issues.append("Skill has no stakeholders defined")

    return issues


def _load_builtin_skills() -> None:
    """Load built-in skills into the registry."""
    if _skills:
        return  # Already loaded

    # Import and register built-in skills
    from sys_audit.skills.code_quality.skill import CodeQualitySkill

    register_skill(CodeQualitySkill())

    # Future skills:
    # from sys_audit.skills.architecture.skill import ArchitectureSkill
    # from sys_audit.skills.dependencies.skill import DependencySkill
    # from sys_audit.skills.testing.skill import TestingSkill
