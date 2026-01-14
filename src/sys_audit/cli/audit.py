"""Audit management CLI commands."""

import asyncio

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer()
console = Console()


@app.command("run")
def run_audit(
    project_name: str = typer.Argument(..., help="Project name to audit"),
    skills: str | None = typer.Option(
        None, "--skills", "-s", help="Comma-separated list of skills to run (default: all)"
    ),
    config: str | None = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    ),
) -> None:
    """Run an audit against a project."""
    from datetime import datetime

    from sqlalchemy import select

    from sys_audit.core.orchestrator import Orchestrator
    from sys_audit.db.models import Audit, AuditStatus, Project
    from sys_audit.db.session import get_session

    skill_list = skills.split(",") if skills else None

    async def _run_audit() -> Audit:
        async with get_session() as session:
            # Find project
            result = await session.execute(
                select(Project).where(Project.name == project_name)
            )
            project = result.scalar_one_or_none()

            if not project:
                raise ValueError(f"Project not found: {project_name}")

            # Create audit record
            audit = Audit(
                project_id=project.id,
                status=AuditStatus.PENDING,
                config={"skills": skill_list} if skill_list else {},
            )
            session.add(audit)
            await session.flush()

            # Run orchestrator
            orchestrator = Orchestrator()

            audit.status = AuditStatus.RUNNING
            audit.started_at = datetime.now()
            await session.flush()

            try:
                findings = await orchestrator.run_audit(
                    repo_path=project.repo_path,
                    skills=skill_list,
                )

                # Save findings
                for finding in findings:
                    finding.audit_id = audit.id
                    session.add(finding)

                audit.status = AuditStatus.COMPLETED
                audit.completed_at = datetime.now()
                audit.summary = {
                    "total_findings": len(findings),
                    "by_severity": _count_by_severity(findings),
                    "by_skill": _count_by_skill(findings),
                }

            except Exception as e:
                audit.status = AuditStatus.FAILED
                audit.error_message = str(e)
                raise

            return audit

    def _count_by_severity(findings: list) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in findings:
            severity = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            counts[severity] = counts.get(severity, 0) + 1
        return counts

    def _count_by_skill(findings: list) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in findings:
            counts[f.skill_name] = counts.get(f.skill_name, 0) + 1
        return counts

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Auditing {project_name}...", total=None)

        try:
            audit = asyncio.run(_run_audit())
            progress.update(task, completed=True)

            console.print("\n[green]Audit completed![/green]")
            console.print(f"  Audit ID: {audit.id}")
            if audit.summary:
                console.print(f"  Total findings: {audit.summary.get('total_findings', 0)}")
                by_severity = audit.summary.get("by_severity", {})
                if by_severity:
                    console.print("  By severity:")
                    for sev, count in by_severity.items():
                        color = _severity_color(sev)
                        console.print(f"    [{color}]{sev}[/{color}]: {count}")

        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Audit failed:[/red] {e}")
            raise typer.Exit(1)


def _severity_color(severity: str) -> str:
    colors = {
        "critical": "red bold",
        "high": "red",
        "medium": "yellow",
        "low": "blue",
        "info": "dim",
    }
    return colors.get(severity.lower(), "white")


@app.command("status")
def audit_status(
    audit_id: str = typer.Argument(..., help="Audit ID to check"),
) -> None:
    """Check the status of an audit."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from sys_audit.db.models import Audit
    from sys_audit.db.session import get_session

    async def _status() -> Audit | None:
        async with get_session() as session:
            result = await session.execute(
                select(Audit).where(Audit.id == audit_id).options(selectinload(Audit.findings))
            )
            return result.scalar_one_or_none()

    try:
        audit = asyncio.run(_status())
        if not audit:
            console.print(f"[red]Audit not found:[/red] {audit_id}")
            raise typer.Exit(1)

        status_color = {
            "pending": "yellow",
            "running": "blue",
            "completed": "green",
            "failed": "red",
        }.get(audit.status.value, "white")

        console.print(f"[bold]Audit {audit.id}[/bold]")
        console.print(f"  Status: [{status_color}]{audit.status.value}[/{status_color}]")
        if audit.started_at:
            console.print(f"  Started: {audit.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if audit.completed_at:
            console.print(f"  Completed: {audit.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if audit.error_message:
            console.print(f"  Error: [red]{audit.error_message}[/red]")
        if audit.summary:
            console.print(f"  Findings: {audit.summary.get('total_findings', 0)}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("history")
def audit_history(
    project_name: str = typer.Argument(..., help="Project name"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of audits to show"),
) -> None:
    """Show audit history for a project."""
    from sqlalchemy import select

    from sys_audit.db.models import Audit, Project
    from sys_audit.db.session import get_session

    async def _history() -> list[Audit]:
        async with get_session() as session:
            result = await session.execute(
                select(Project).where(Project.name == project_name)
            )
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project not found: {project_name}")

            result = await session.execute(
                select(Audit)
                .where(Audit.project_id == project.id)
                .order_by(Audit.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    try:
        audits = asyncio.run(_history())

        if not audits:
            console.print(f"[yellow]No audits found for project:[/yellow] {project_name}")
            return

        table = Table(title=f"Audit History: {project_name}")
        table.add_column("ID", style="dim")
        table.add_column("Status")
        table.add_column("Findings")
        table.add_column("Started")
        table.add_column("Duration")

        for audit in audits:
            status_color = _severity_color(audit.status.value)
            findings = audit.summary.get("total_findings", "-") if audit.summary else "-"
            started = audit.started_at.strftime("%Y-%m-%d %H:%M") if audit.started_at else "-"

            duration = "-"
            if audit.started_at and audit.completed_at:
                delta = audit.completed_at - audit.started_at
                duration = f"{delta.seconds}s"

            table.add_row(
                audit.id[:8] + "...",
                f"[{status_color}]{audit.status.value}[/{status_color}]",
                str(findings),
                started,
                duration,
            )

        console.print(table)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
