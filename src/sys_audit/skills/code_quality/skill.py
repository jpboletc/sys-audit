"""Code quality analysis skill using ruff and LLM."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from sys_audit.db.models import EffortEstimate, Finding, FindingSource, Severity
from sys_audit.skills.base import AnalysisContext, BaseSkill


@dataclass
class ComplexityMetrics:
    """Complexity metrics for a file."""

    file_path: str
    cyclomatic: int
    loc: int
    functions: list[dict[str, Any]]


class LLMFinding(BaseModel):
    """Schema for LLM-generated findings."""

    title: str
    severity: str
    start_line: int | None = None
    end_line: int | None = None
    explanation: str
    refactoring_suggestion: str
    effort: str
    confidence: float = 0.8


class LLMFindings(BaseModel):
    """Schema for LLM response."""

    findings: list[LLMFinding]


class CodeQualitySkill(BaseSkill):
    """Analyzes code for complexity, smells, and maintainability."""

    name = "code-quality"
    version = "1.0.0"
    description = "Analyzes code for complexity, smells, and maintainability"
    stakeholders = ["developer", "tech-lead"]
    static_tools = ["ruff", "radon"]

    # Ruff rule severity mapping
    RUFF_SEVERITY_MAP = {
        "E": Severity.MEDIUM,  # pycodestyle errors
        "W": Severity.LOW,  # pycodestyle warnings
        "F": Severity.HIGH,  # pyflakes
        "C": Severity.MEDIUM,  # complexity
        "I": Severity.LOW,  # isort
        "N": Severity.LOW,  # naming
        "D": Severity.LOW,  # docstrings
        "UP": Severity.LOW,  # pyupgrade
        "B": Severity.MEDIUM,  # bugbear
        "A": Severity.MEDIUM,  # builtins
        "S": Severity.HIGH,  # bandit security
        "T": Severity.LOW,  # print statements
        "Q": Severity.LOW,  # quotes
        "ARG": Severity.LOW,  # unused arguments
        "PTH": Severity.LOW,  # pathlib
        "ERA": Severity.LOW,  # commented out code
        "PL": Severity.MEDIUM,  # pylint
        "TRY": Severity.MEDIUM,  # tryceratops
        "RUF": Severity.MEDIUM,  # ruff specific
    }

    async def analyze(
        self,
        context: AnalysisContext,
        llm: Any,
    ) -> list[Finding]:
        """Run code quality analysis."""
        findings: list[Finding] = []

        # Stage 1: Static Analysis
        ruff_findings = await self._run_ruff(context.repo_path)
        findings.extend(ruff_findings)

        complexity_metrics = await self._calculate_complexity(context.repo_path)

        # Stage 2: LLM Analysis for complex files
        high_complexity_files = [
            m for m in complexity_metrics
            if m.cyclomatic > context.config.complexity_threshold
        ]

        for metrics in high_complexity_files[:5]:  # Limit to 5 files to avoid overwhelming LLM
            llm_findings = await self._analyze_with_llm(context, llm, metrics)
            findings.extend(llm_findings)

        # Stage 3: Synthesis - deduplicate
        findings = self._deduplicate(findings)

        return findings

    async def _run_ruff(self, repo_path: Path) -> list[Finding]:
        """Run ruff linter and convert to findings."""
        findings = []

        try:
            result = subprocess.run(
                ["ruff", "check", "--output-format=json", str(repo_path)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.stdout:
                issues = json.loads(result.stdout)

                for issue in issues:
                    code = issue.get("code", "")
                    severity = self._get_ruff_severity(code)

                    findings.append(self.create_finding(
                        title=issue.get("message", "Linting issue"),
                        severity=severity,
                        category="linting",
                        file_path=issue.get("filename"),
                        line_start=issue.get("location", {}).get("row"),
                        line_end=issue.get("end_location", {}).get("row"),
                        recommendation=self._get_ruff_recommendation(code),
                        source=FindingSource.STATIC,
                        confidence=1.0,
                        metadata={"ruff_code": code},
                    ))

        except FileNotFoundError:
            # ruff not installed, skip
            pass
        except subprocess.TimeoutExpired:
            pass
        except json.JSONDecodeError:
            pass

        return findings

    def _get_ruff_severity(self, code: str) -> Severity:
        """Map ruff rule code to severity."""
        for prefix, severity in self.RUFF_SEVERITY_MAP.items():
            if code.startswith(prefix):
                return severity
        return Severity.MEDIUM

    def _get_ruff_recommendation(self, code: str) -> str:
        """Get recommendation for ruff rule."""
        recommendations = {
            "E": "Fix the style issue to improve code consistency",
            "W": "Consider fixing this warning for cleaner code",
            "F": "This is a likely bug - fix immediately",
            "B": "This pattern is error-prone - refactor for safety",
            "S": "Security issue - review and fix",
            "C90": "Reduce function complexity by extracting methods",
        }
        for prefix, rec in recommendations.items():
            if code.startswith(prefix):
                return rec
        return "Review and fix if appropriate"

    async def _calculate_complexity(self, repo_path: Path) -> list[ComplexityMetrics]:
        """Calculate complexity metrics using radon."""
        metrics = []

        try:
            result = subprocess.run(
                ["radon", "cc", "-j", str(repo_path)],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.stdout:
                data = json.loads(result.stdout)

                for file_path, functions in data.items():
                    if not functions:
                        continue

                    # Calculate file-level complexity as sum of function complexities
                    total_complexity = sum(f.get("complexity", 0) for f in functions)

                    metrics.append(ComplexityMetrics(
                        file_path=file_path,
                        cyclomatic=total_complexity,
                        loc=sum(f.get("endline", 0) - f.get("lineno", 0) for f in functions),
                        functions=functions,
                    ))

        except FileNotFoundError:
            # radon not installed, skip
            pass
        except subprocess.TimeoutExpired:
            pass
        except json.JSONDecodeError:
            pass

        return metrics

    async def _analyze_with_llm(
        self,
        context: AnalysisContext,
        llm: Any,
        metrics: ComplexityMetrics,
    ) -> list[Finding]:
        """Analyze a high-complexity file with LLM."""
        findings = []

        try:
            code = await context.read_file(metrics.file_path)
        except FileNotFoundError:
            return findings

        language = context.detect_language(metrics.file_path)

        prompt = f"""You are an expert code reviewer analyzing {language} code for maintainability issues.

## Code to Review

File: {metrics.file_path}
Cyclomatic Complexity: {metrics.cyclomatic}
Lines of Code: {metrics.loc}

```{language}
{code[:8000]}  # Truncate to fit context window
```

## Your Task

Identify specific maintainability issues in this code. For each issue:
1. Explain WHY it's a problem (not just what)
2. Suggest a concrete refactoring approach
3. Rate severity: critical/high/medium/low
4. Estimate effort: trivial/small/medium/large

Focus on:
- Functions doing too many things
- Deep nesting that harms readability
- Unclear variable/function names
- Missing abstractions
- Code that would be hard to test

## Response Format

Return JSON only:
```json
{{
  "findings": [
    {{
      "title": "Brief issue title",
      "severity": "high",
      "start_line": 15,
      "end_line": 45,
      "explanation": "Why this is problematic...",
      "refactoring_suggestion": "Extract method for...",
      "effort": "medium",
      "confidence": 0.85
    }}
  ]
}}
```

Be specific. Reference actual line numbers. Limit to 5 most important issues."""

        try:
            response = await llm.analyze(prompt, response_format=LLMFindings)

            if isinstance(response, LLMFindings):
                for llm_finding in response.findings:
                    effort = self._parse_effort(llm_finding.effort)
                    severity = self._parse_severity(llm_finding.severity)

                    findings.append(self.create_finding(
                        title=llm_finding.title,
                        severity=severity,
                        category="complexity",
                        description=llm_finding.explanation,
                        file_path=metrics.file_path,
                        line_start=llm_finding.start_line,
                        line_end=llm_finding.end_line,
                        recommendation=llm_finding.refactoring_suggestion,
                        effort_estimate=effort,
                        source=FindingSource.LLM,
                        confidence=llm_finding.confidence,
                    ))

        except Exception:
            # LLM analysis failed, continue without
            pass

        return findings

    def _parse_effort(self, effort: str) -> EffortEstimate:
        """Parse effort string to enum."""
        effort_map = {
            "trivial": EffortEstimate.TRIVIAL,
            "small": EffortEstimate.SMALL,
            "medium": EffortEstimate.MEDIUM,
            "large": EffortEstimate.LARGE,
        }
        return effort_map.get(effort.lower(), EffortEstimate.MEDIUM)

    def _parse_severity(self, severity: str) -> Severity:
        """Parse severity string to enum."""
        severity_map = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
        }
        return severity_map.get(severity.lower(), Severity.MEDIUM)

    def _deduplicate(self, findings: list[Finding]) -> list[Finding]:
        """Remove duplicate findings based on file and line."""
        seen: set[tuple[str | None, int | None, str]] = set()
        unique: list[Finding] = []

        for finding in findings:
            key = (finding.file_path, finding.line_start, finding.title[:50])
            if key not in seen:
                seen.add(key)
                unique.append(finding)

        return unique

    def get_prompts(self) -> dict[str, str]:
        """Get available prompt templates."""
        return {
            "complexity_review": "complexity_review.j2",
            "naming_review": "naming_review.j2",
        }
