# sys-audit Project Instructions

## Project Overview

AI-driven codebase quality analysis tool for consultancy handovers. Uses local LLMs (Qwen Coder via Ollama) to provide consultant-grade code auditing while keeping all data local.

## Tech Stack

- **Language**: Python 3.12+
- **CLI**: Typer + Rich
- **Web API**: FastAPI + Uvicorn
- **Database**: PostgreSQL 16 + SQLAlchemy 2.0 + Alembic
- **LLM**: Ollama (Qwen2.5-Coder-7B default)
- **Static Analysis**: ruff, radon

## Project Structure

```
src/sys_audit/
├── cli/          # Typer CLI commands
├── api/          # FastAPI web API (placeholder)
├── core/         # Business logic (orchestrator, config, standalone, reporter)
├── skills/       # Analysis skills (modular analyzers)
├── llm/          # Ollama client and prompt management
├── parsers/      # Code parsing utilities (placeholder)
├── db/           # SQLAlchemy models and repositories
└── integrations/ # External integrations (placeholder)

prompts/          # Jinja2 prompt templates (hot-reloadable)
tests/            # Unit and integration tests
alembic/          # Database migrations
```

## Quick Start

```bash
# Install dependencies
uv sync

# Analyze any codebase immediately (no database/Ollama required)
uv run sys-audit analyze ./path/to/repo --no-llm

# Save report to file
uv run sys-audit analyze . --output report.md

# Self-check (analyze sys-audit itself)
uv run sys-audit self-check

# With LLM analysis (requires Ollama running)
uv run sys-audit analyze ./path/to/repo
```

## All CLI Commands

```bash
uv run sys-audit --help           # Show all commands
uv run sys-audit version          # Show version
uv run sys-audit analyze <path>   # Standalone analysis
uv run sys-audit self-check       # Analyze sys-audit itself
uv run sys-audit skills list      # List available skills
uv run sys-audit skills info <n>  # Show skill details
uv run sys-audit serve            # Start web dashboard (not yet implemented)

# Database-backed commands (require PostgreSQL)
uv run sys-audit project add <path>
uv run sys-audit project list
uv run sys-audit audit run <project>
uv run sys-audit report generate <audit-id>
```

## Development Commands

```bash
# Linting and formatting
uv run ruff check src/
uv run ruff check src/ --fix
uv run ruff format src/

# Type checking
uv run mypy src/

# Run tests
uv run pytest

# Database migrations (requires PostgreSQL)
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"
```

## Key Patterns

### Skills Architecture

Skills follow a three-stage pipeline:
1. **Static Collection** - Run deterministic tools (ruff, radon)
2. **LLM Analysis** - Apply prompts with collected context
3. **Synthesis** - Merge findings, deduplicate, score confidence

Each skill implements:
```python
class BaseSkill(ABC):
    name: str
    version: str
    stakeholders: list[str]

    async def analyze(self, context: AnalysisContext, llm: LLMClient) -> list[Finding]
```

### Findings

All findings include:
- `source`: "static" | "llm" | "combined"
- `confidence`: 0.0-1.0 score
- `severity`: "critical" | "high" | "medium" | "low" | "info"
- `file_path` and `line_start`/`line_end`
- `recommendation` and `effort_estimate`

### Database Models

Using async SQLAlchemy with asyncpg. Models in `db/models.py`:
- `Project` - Registered codebases
- `Audit` - Analysis runs
- `Finding` - Individual issues found
- `Score` - Per-skill scores per audit
- `WorkItem` - Links to external issue trackers

## Environment Variables

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/sys_audit
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b
```

See `.env.example` for all options.

---

## Current Status

Phase 1 is COMPLETE - Standalone analysis works without external dependencies.

Ready to resume: Phase 2 (Core Skills)

---

## Implementation Phases

### Phase 1: Foundation (MVP) - COMPLETE ✓

1. [x] Project scaffolding with uv/pyproject.toml
2. [x] Database models (Project, Audit, Finding, Score, WorkItem)
3. [x] Alembic migrations setup
4. [x] CLI skeleton with Typer (project, audit, report, skills commands)
5. [x] Ollama LLM client
6. [x] Skill framework base classes
7. [x] First skill: code-quality (ruff + radon + LLM)
8. [x] Markdown/JSON report generation
9. [x] Standalone analyze command (no DB required)
10. [x] Self-check command

### Phase 2: Core Skills - NEXT

1. [ ] architecture-review skill (layer detection, coupling, patterns)
2. [ ] dependency-health skill (outdated deps, CVE checking)
3. [ ] test-coverage skill (coverage metrics, test quality)
4. [ ] Scoring system implementation
5. [ ] HTML report generation

### Phase 3: Web Interface

1. [ ] FastAPI backend routes
2. [ ] React dashboard scaffold
3. [ ] Project/audit list views
4. [ ] Finding detail view with code context
5. [ ] Stakeholder-filtered views

### Phase 4: DevOps Skills

1. [ ] cicd-review skill (GitLab, Jenkins, GitHub Actions)
2. [ ] iac-cost-estimation skill (Terraform, CloudFormation)
3. [ ] documentation-quality skill
4. [ ] security-audit skill

### Phase 5: Integrations

1. [ ] GitHub Issues integration
2. [ ] Jira integration
3. [ ] Audit comparison and trend tracking

---

## Implemented Skills

### code-quality ✓

- **Static tools**: ruff linting, radon complexity metrics
- **LLM**: Deep complexity analysis for high-complexity files
- **Stakeholders**: developer, tech-lead
- **Location**: `src/sys_audit/skills/code_quality/skill.py`

---

## Planned Skills

### architecture-review (Phase 2)

- Static: pydeps dependency graphs, import-linter
- LLM: Pattern detection, layer analysis, coupling assessment
- Stakeholders: architect, tech-lead

### dependency-health (Phase 2)

- Static: pip-audit, npm audit, safety
- LLM: Update risk assessment
- Stakeholders: developer, security

### test-coverage (Phase 2)

- Static: coverage.py, pytest-cov
- LLM: Test quality review, edge case detection
- Stakeholders: developer, qa

---

## Notes

- Prompts stored separately in `prompts/` for hot-reload
- All code analysis stays local - privacy first
- Confidence scoring: static=1.0, LLM with examples=0.8-0.95, LLM inference=0.6-0.8
- Languages supported: Python, Java, JavaScript/TypeScript

## Key Files

- `src/sys_audit/cli/main.py` - CLI entry point
- `src/sys_audit/core/standalone.py` - Standalone analysis (no DB)
- `src/sys_audit/core/orchestrator.py` - Skill coordination
- `src/sys_audit/skills/base.py` - Skill base class
- `src/sys_audit/skills/code_quality/skill.py` - Code quality skill
- `src/sys_audit/llm/client.py` - Ollama client
- `src/sys_audit/db/models.py` - Database models

## Full Plan Document

See `~/.claude/plans/quiet-tickling-aho.md` for the complete architectural plan including trust strategy, evolution plans, and detailed skill designs.
