"""Standalone analysis without database dependency."""

import json
from datetime import datetime
from pathlib import Path

from sys_audit.core.config import get_settings
from sys_audit.db.models import Finding
from sys_audit.llm.client import OllamaClient
from sys_audit.skills import get_available_skills, get_skill_by_name
from sys_audit.skills.base import AnalysisContext


class MockLLMClient:
    """Mock LLM client that skips LLM analysis."""

    async def analyze(self, *args, **kwargs) -> dict:
        return {"findings": [], "skipped": True}

    async def generate(self, *args, **kwargs):
        raise RuntimeError("LLM disabled")

    async def is_available(self) -> bool:
        return False


async def run_standalone_analysis(
    repo_path: Path,
    skills: list[str] | None = None,
    output_format: str = "markdown",
    use_llm: bool = True,
) -> str:
    """Run analysis without database, return formatted report.

    Args:
        repo_path: Path to the repository to analyze
        skills: List of skill names to run, or None for all
        output_format: Output format (markdown, json)
        use_llm: Whether to use LLM analysis

    Returns:
        Formatted report string
    """
    settings = get_settings()

    # Set up LLM client
    if use_llm:
        llm_client = OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout=settings.ollama_timeout,
        )
        # Check if Ollama is available
        if not await llm_client.is_available():
            llm_client = MockLLMClient()
    else:
        llm_client = MockLLMClient()

    # Get skills to run
    if skills:
        skill_instances = [get_skill_by_name(name) for name in skills]
        skill_instances = [s for s in skill_instances if s is not None]
    else:
        skill_instances = get_available_skills()

    if not skill_instances:
        raise ValueError("No skills available for analysis")

    # Create analysis context
    context = AnalysisContext(
        repo_path=repo_path,
        config=settings,
    )

    # Run each skill and collect findings
    all_findings: list[Finding] = []
    skills_run: list[str] = []

    for skill in skill_instances:
        try:
            findings = await skill.analyze(context, llm_client)
            all_findings.extend(findings)
            skills_run.append(skill.name)
        except Exception as e:
            # Log but continue
            print(f"Warning: Skill {skill.name} failed: {e}")

    # Filter by minimum confidence
    all_findings = [
        f for f in all_findings if f.confidence >= settings.min_confidence
    ]

    # Format output
    if output_format == "json":
        return _format_json(repo_path, all_findings, skills_run)
    else:
        return _format_markdown(repo_path, all_findings, skills_run)


def _format_markdown(
    repo_path: Path,
    findings: list[Finding],
    skills_run: list[str],
) -> str:
    """Format findings as markdown report."""
    lines = [
        f"# Code Analysis Report: {repo_path.name}",
        "",
        f"**Path:** `{repo_path}`",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Skills:** {', '.join(skills_run)}",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"Total findings: **{len(findings)}**",
        "",
    ]

    # Count by severity
    by_severity: dict[str, list[Finding]] = {}
    for f in findings:
        sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        if sev not in by_severity:
            by_severity[sev] = []
        by_severity[sev].append(f)

    if by_severity:
        lines.append("### By Severity")
        lines.append("")
        severity_order = ["critical", "high", "medium", "low", "info"]
        for sev in severity_order:
            if sev in by_severity:
                emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}.get(sev, "⚪")
                lines.append(f"- {emoji} **{sev.title()}**: {len(by_severity[sev])}")
        lines.append("")

    # Count by skill
    by_skill: dict[str, int] = {}
    for f in findings:
        by_skill[f.skill_name] = by_skill.get(f.skill_name, 0) + 1

    if by_skill:
        lines.append("### By Skill")
        lines.append("")
        for skill, count in sorted(by_skill.items()):
            lines.append(f"- **{skill}**: {count}")
        lines.append("")

    # Detailed findings
    if findings:
        lines.append("---")
        lines.append("")
        lines.append("## Findings")
        lines.append("")

        severity_order = ["critical", "high", "medium", "low", "info"]
        for sev in severity_order:
            sev_findings = by_severity.get(sev, [])
            if not sev_findings:
                continue

            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}.get(sev, "⚪")
            lines.append(f"### {emoji} {sev.title()} ({len(sev_findings)})")
            lines.append("")

            for finding in sev_findings[:20]:  # Limit per severity
                lines.append(f"#### {finding.title}")
                lines.append("")

                if finding.file_path:
                    loc = finding.file_path
                    if finding.line_start:
                        loc += f":{finding.line_start}"
                    lines.append(f"**Location:** `{loc}`")

                lines.append(f"**Category:** {finding.category}")
                lines.append(f"**Confidence:** {finding.confidence:.0%}")
                lines.append("")

                if finding.description:
                    lines.append(finding.description)
                    lines.append("")

                if finding.recommendation:
                    lines.append(f"**Recommendation:** {finding.recommendation}")
                    lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Generated by sys-audit v0.1.0*")

    return "\n".join(lines)


def _format_json(
    repo_path: Path,
    findings: list[Finding],
    skills_run: list[str],
) -> str:
    """Format findings as JSON."""
    data = {
        "repo_path": str(repo_path),
        "generated_at": datetime.now().isoformat(),
        "skills_run": skills_run,
        "summary": {
            "total_findings": len(findings),
            "by_severity": {},
            "by_skill": {},
        },
        "findings": [],
    }

    for f in findings:
        sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        data["summary"]["by_severity"][sev] = data["summary"]["by_severity"].get(sev, 0) + 1
        data["summary"]["by_skill"][f.skill_name] = data["summary"]["by_skill"].get(f.skill_name, 0) + 1

        data["findings"].append({
            "skill_name": f.skill_name,
            "severity": sev,
            "category": f.category,
            "title": f.title,
            "description": f.description,
            "file_path": f.file_path,
            "line_start": f.line_start,
            "line_end": f.line_end,
            "recommendation": f.recommendation,
            "confidence": f.confidence,
            "source": f.source.value if hasattr(f.source, "value") else str(f.source),
        })

    return json.dumps(data, indent=2)
