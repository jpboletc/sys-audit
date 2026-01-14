"""Base classes and protocols for analysis skills."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from jinja2 import Environment, FileSystemLoader

from sys_audit.core.config import Settings
from sys_audit.db.models import EffortEstimate, Finding, FindingSource, Severity


@dataclass
class AnalysisContext:
    """Context provided to skills during analysis."""

    repo_path: Path
    config: Settings
    metadata: dict[str, Any] = field(default_factory=dict)

    async def read_file(self, path: str | Path) -> str:
        """Read a file from the repository."""
        full_path = self.repo_path / path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return full_path.read_text(encoding="utf-8", errors="replace")

    def detect_language(self, path: str | Path) -> str:
        """Detect the programming language of a file."""
        suffix_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".java": "java",
            ".kt": "kotlin",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".swift": "swift",
            ".scala": "scala",
            ".sh": "bash",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".sql": "sql",
            ".md": "markdown",
        }
        suffix = Path(path).suffix.lower()
        return suffix_map.get(suffix, "text")


@runtime_checkable
class SkillProtocol(Protocol):
    """Protocol defining the interface for analysis skills."""

    name: str
    version: str
    description: str
    stakeholders: list[str]

    async def analyze(
        self,
        context: AnalysisContext,
        llm: Any,  # OllamaClient, but avoiding circular import
    ) -> list[Finding]: ...

    def get_prompts(self) -> dict[str, str]: ...


class BaseSkill(ABC):
    """Base class for analysis skills."""

    name: str = "base"
    version: str = "0.0.0"
    description: str = "Base skill"
    stakeholders: list[str] = []
    static_tools: list[str] = []

    def __init__(self) -> None:
        self._prompt_env: Environment | None = None

    @abstractmethod
    async def analyze(
        self,
        context: AnalysisContext,
        llm: Any,
    ) -> list[Finding]:
        """Run analysis and return findings.

        Args:
            context: Analysis context with repo path and config
            llm: LLM client for AI-powered analysis

        Returns:
            List of findings from the analysis
        """
        ...

    def get_prompts(self) -> dict[str, str]:
        """Get available prompt templates for this skill.

        Returns:
            Dict mapping prompt names to their paths/content
        """
        return {}

    def _get_prompt_env(self, prompts_dir: Path) -> Environment:
        """Get or create Jinja2 environment for prompts."""
        if self._prompt_env is None:
            skill_prompts_dir = prompts_dir / self.name.replace("-", "_")
            if skill_prompts_dir.exists():
                self._prompt_env = Environment(
                    loader=FileSystemLoader(skill_prompts_dir),
                    autoescape=False,
                )
            else:
                # Fallback to empty environment
                self._prompt_env = Environment(autoescape=False)
        return self._prompt_env

    def render_prompt(
        self,
        template_name: str,
        prompts_dir: Path,
        **context: Any,
    ) -> str:
        """Render a prompt template with context.

        Args:
            template_name: Name of the template file (e.g., "analysis.j2")
            prompts_dir: Directory containing prompt templates
            **context: Variables to pass to the template

        Returns:
            Rendered prompt string
        """
        env = self._get_prompt_env(prompts_dir)
        try:
            template = env.get_template(template_name)
            return template.render(**context)
        except Exception:
            # Template not found, return empty string
            return ""

    def create_finding(
        self,
        title: str,
        severity: Severity | str,
        category: str,
        description: str | None = None,
        file_path: str | None = None,
        line_start: int | None = None,
        line_end: int | None = None,
        code_snippet: str | None = None,
        recommendation: str | None = None,
        effort_estimate: EffortEstimate | str | None = None,
        source: FindingSource | str = FindingSource.STATIC,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> Finding:
        """Helper to create a Finding with this skill's name.

        Args:
            title: Short title for the finding
            severity: Severity level
            category: Category within the skill
            description: Detailed description
            file_path: Path to the affected file
            line_start: Starting line number
            line_end: Ending line number
            code_snippet: Relevant code snippet
            recommendation: Suggested fix
            effort_estimate: Estimated effort to fix
            source: Source of the finding (static, llm, combined)
            confidence: Confidence score (0.0-1.0)
            metadata: Additional metadata

        Returns:
            A Finding instance
        """
        # Convert string enums to enum values
        if isinstance(severity, str):
            severity = Severity(severity.lower())
        if isinstance(source, str):
            source = FindingSource(source.lower())
        if isinstance(effort_estimate, str):
            effort_estimate = EffortEstimate(effort_estimate.lower())

        return Finding(
            skill_name=self.name,
            severity=severity,
            category=category,
            title=title,
            description=description,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            code_snippet=code_snippet,
            recommendation=recommendation,
            effort_estimate=effort_estimate,
            source=source,
            confidence=confidence,
            stakeholders=self.stakeholders,
            metadata_=metadata or {},
        )
