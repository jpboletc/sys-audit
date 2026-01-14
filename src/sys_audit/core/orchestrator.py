"""Orchestrator that coordinates skill execution."""

from pathlib import Path

from sys_audit.core.config import get_settings
from sys_audit.db.models import Finding
from sys_audit.llm.client import OllamaClient
from sys_audit.skills import get_available_skills, get_skill_by_name
from sys_audit.skills.base import AnalysisContext, BaseSkill


class Orchestrator:
    """Coordinates skill execution for codebase analysis."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_client = OllamaClient(
            base_url=self.settings.ollama_base_url,
            model=self.settings.ollama_model,
            timeout=self.settings.ollama_timeout,
        )

    async def run_audit(
        self,
        repo_path: str,
        skills: list[str] | None = None,
    ) -> list[Finding]:
        """Run an audit against a repository.

        Args:
            repo_path: Path to the repository to analyze
            skills: List of skill names to run, or None for all

        Returns:
            List of findings from all skills
        """
        path = Path(repo_path)
        if not path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        # Get skills to run
        if skills:
            skill_instances = [get_skill_by_name(name) for name in skills]
            skill_instances = [s for s in skill_instances if s is not None]
            if not skill_instances:
                raise ValueError(f"No valid skills found: {skills}")
        else:
            skill_instances = get_available_skills()

        if not skill_instances:
            raise ValueError("No skills available for analysis")

        # Create analysis context
        context = AnalysisContext(
            repo_path=path,
            config=self.settings,
        )

        # Run each skill and collect findings
        all_findings: list[Finding] = []

        for skill in skill_instances:
            findings = await self._run_skill(skill, context)
            all_findings.extend(findings)

        # Filter by minimum confidence
        all_findings = [
            f for f in all_findings if f.confidence >= self.settings.min_confidence
        ]

        return all_findings

    async def _run_skill(
        self,
        skill: BaseSkill,
        context: AnalysisContext,
    ) -> list[Finding]:
        """Run a single skill and return its findings."""
        try:
            findings = await skill.analyze(context, self.llm_client)
            return findings
        except Exception as e:
            # Log error but don't fail entire audit
            # In production, this should use proper logging
            print(f"Error running skill {skill.name}: {e}")
            return []
