"""Main CLI application entry point."""

import typer
from rich.console import Console

from sys_audit.cli import audit, project, report, skills

app = typer.Typer(
    name="sys-audit",
    help="AI-driven codebase quality analysis tool",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

# Register sub-commands
app.add_typer(project.app, name="project", help="Manage projects")
app.add_typer(audit.app, name="audit", help="Run and manage audits")
app.add_typer(report.app, name="report", help="Generate reports")
app.add_typer(skills.app, name="skills", help="Manage analysis skills")


@app.command()
def version() -> None:
    """Show version information."""
    from sys_audit import __version__

    console.print(f"[bold]sys-audit[/bold] version {__version__}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8080, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
) -> None:
    """Start the web dashboard server."""
    import uvicorn

    console.print(f"[bold green]Starting sys-audit server[/bold green] at http://{host}:{port}")
    uvicorn.run(
        "sys_audit.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command(name="self-check")
def self_check() -> None:
    """Run sys-audit on itself as a validation check."""
    import os
    # Find the project root (where pyproject.toml is)
    current = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    analyze(path=current, skills=None, output=None, format="markdown", no_llm=True)


@app.command()
def analyze(
    path: str = typer.Argument(..., help="Path to the codebase to analyze"),
    skills: str | None = typer.Option(
        None, "--skills", "-s", help="Comma-separated list of skills (default: all)"
    ),
    output: str | None = typer.Option(
        None, "--output", "-o", help="Output file path (default: stdout)"
    ),
    format: str = typer.Option(
        "markdown", "--format", "-f", help="Output format: markdown, json"
    ),
    no_llm: bool = typer.Option(
        False, "--no-llm", help="Skip LLM analysis (static tools only)"
    ),
) -> None:
    """Analyze a codebase without database (standalone mode)."""
    import asyncio
    from pathlib import Path

    from rich.progress import Progress, SpinnerColumn, TextColumn

    from sys_audit.core.standalone import run_standalone_analysis

    repo_path = Path(path).resolve()
    if not repo_path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {path}")
        raise typer.Exit(1)

    if not repo_path.is_dir():
        console.print(f"[red]Error:[/red] Path is not a directory: {path}")
        raise typer.Exit(1)

    skill_list = skills.split(",") if skills else None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Analyzing {repo_path.name}...", total=None)

        try:
            result = asyncio.run(
                run_standalone_analysis(
                    repo_path=repo_path,
                    skills=skill_list,
                    output_format=format,
                    use_llm=not no_llm,
                )
            )
            progress.update(task, completed=True)

            if output:
                Path(output).write_text(result)
                console.print(f"\n[green]Report saved to:[/green] {output}")
            else:
                console.print()
                console.print(result)

        except Exception as e:
            console.print(f"\n[red]Analysis failed:[/red] {e}")
            raise typer.Exit(1)


if __name__ == "__main__":
    app()
