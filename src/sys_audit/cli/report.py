"""Report generation CLI commands."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer()
console = Console()


@app.command("generate")
def generate_report(
    audit_id: str = typer.Argument(..., help="Audit ID to generate report for"),
    format: str = typer.Option("markdown", "--format", "-f", help="Output format: markdown, html, json"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file path"),
    stakeholder: str | None = typer.Option(
        None, "--stakeholder", "-s", help="Filter for stakeholder: architect, developer, manager"
    ),
) -> None:
    """Generate a report from audit results."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from sys_audit.core.reporter import ReportGenerator
    from sys_audit.db.models import Audit
    from sys_audit.db.session import get_session

    async def _generate() -> str:
        async with get_session() as session:
            result = await session.execute(
                select(Audit)
                .where(Audit.id == audit_id)
                .options(
                    selectinload(Audit.findings),
                    selectinload(Audit.scores),
                    selectinload(Audit.project),
                )
            )
            audit = result.scalar_one_or_none()

            if not audit:
                raise ValueError(f"Audit not found: {audit_id}")

            generator = ReportGenerator()
            return generator.generate(
                audit=audit,
                format=format,
                stakeholder=stakeholder,
            )

    try:
        report = asyncio.run(_generate())

        if output:
            output.write_text(report)
            console.print(f"[green]Report saved to:[/green] {output}")
        else:
            console.print(report)

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error generating report:[/red] {e}")
        raise typer.Exit(1)


@app.command("compare")
def compare_audits(
    audit_id_1: str = typer.Argument(..., help="First audit ID (older)"),
    audit_id_2: str = typer.Argument(..., help="Second audit ID (newer)"),
    format: str = typer.Option("markdown", "--format", "-f", help="Output format"),
) -> None:
    """Compare two audits to show progress."""
    console.print("[yellow]Compare not yet implemented[/yellow]")
    console.print(f"Would compare {audit_id_1[:8]}... with {audit_id_2[:8]}...")
