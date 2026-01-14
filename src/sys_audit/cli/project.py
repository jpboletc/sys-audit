"""Project management CLI commands."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()


@app.command("add")
def add_project(
    path: Path = typer.Argument(..., help="Path to the repository"),
    name: str = typer.Option(None, "--name", "-n", help="Project name (defaults to directory name)"),
    description: str = typer.Option(None, "--description", "-d", help="Project description"),
    url: str = typer.Option(None, "--url", "-u", help="Repository URL"),
) -> None:
    """Register a new project for analysis."""
    from sys_audit.db.models import Project
    from sys_audit.db.session import get_session

    if not path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {path}")
        raise typer.Exit(1)

    if not path.is_dir():
        console.print(f"[red]Error:[/red] Path is not a directory: {path}")
        raise typer.Exit(1)

    project_name = name or path.name
    repo_path = str(path.resolve())

    async def _add() -> Project:
        async with get_session() as session:
            project = Project(
                name=project_name,
                repo_path=repo_path,
                repo_url=url,
                description=description,
            )
            session.add(project)
            await session.flush()
            return project

    try:
        project = asyncio.run(_add())
        console.print(f"[green]Added project:[/green] {project.name}")
        console.print(f"  ID: {project.id}")
        console.print(f"  Path: {project.repo_path}")
    except Exception as e:
        console.print(f"[red]Error adding project:[/red] {e}")
        raise typer.Exit(1)


@app.command("list")
def list_projects() -> None:
    """List all registered projects."""
    from sqlalchemy import select

    from sys_audit.db.models import Project
    from sys_audit.db.session import get_session

    async def _list() -> list[Project]:
        async with get_session() as session:
            result = await session.execute(select(Project).order_by(Project.name))
            return list(result.scalars().all())

    try:
        projects = asyncio.run(_list())

        if not projects:
            console.print("[yellow]No projects registered.[/yellow]")
            console.print("Use 'sys-audit project add <path>' to add one.")
            return

        table = Table(title="Registered Projects")
        table.add_column("Name", style="cyan")
        table.add_column("Path")
        table.add_column("Created")

        for project in projects:
            table.add_row(
                project.name,
                project.repo_path,
                project.created_at.strftime("%Y-%m-%d %H:%M"),
            )

        console.print(table)
    except Exception as e:
        console.print(f"[red]Error listing projects:[/red] {e}")
        raise typer.Exit(1)


@app.command("remove")
def remove_project(
    name: str = typer.Argument(..., help="Project name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Remove a registered project."""
    from sqlalchemy import delete, select

    from sys_audit.db.models import Project
    from sys_audit.db.session import get_session

    async def _remove() -> bool:
        async with get_session() as session:
            result = await session.execute(select(Project).where(Project.name == name))
            project = result.scalar_one_or_none()

            if not project:
                return False

            await session.execute(delete(Project).where(Project.id == project.id))
            return True

    if not force:
        confirm = typer.confirm(f"Remove project '{name}' and all its audits?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    try:
        removed = asyncio.run(_remove())
        if removed:
            console.print(f"[green]Removed project:[/green] {name}")
        else:
            console.print(f"[red]Project not found:[/red] {name}")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error removing project:[/red] {e}")
        raise typer.Exit(1)


@app.command("show")
def show_project(
    name: str = typer.Argument(..., help="Project name to show"),
) -> None:
    """Show details for a project."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import selectinload

    from sys_audit.db.models import Audit, Project
    from sys_audit.db.session import get_session

    async def _show() -> tuple[Project | None, int]:
        async with get_session() as session:
            result = await session.execute(
                select(Project).where(Project.name == name).options(selectinload(Project.audits))
            )
            project = result.scalar_one_or_none()
            if not project:
                return None, 0

            count_result = await session.execute(
                select(func.count()).select_from(Audit).where(Audit.project_id == project.id)
            )
            audit_count = count_result.scalar() or 0
            return project, audit_count

    try:
        project, audit_count = asyncio.run(_show())
        if not project:
            console.print(f"[red]Project not found:[/red] {name}")
            raise typer.Exit(1)

        console.print(f"[bold cyan]{project.name}[/bold cyan]")
        console.print(f"  ID: {project.id}")
        console.print(f"  Path: {project.repo_path}")
        if project.repo_url:
            console.print(f"  URL: {project.repo_url}")
        if project.description:
            console.print(f"  Description: {project.description}")
        console.print(f"  Created: {project.created_at.strftime('%Y-%m-%d %H:%M')}")
        console.print(f"  Audits: {audit_count}")
    except Exception as e:
        console.print(f"[red]Error showing project:[/red] {e}")
        raise typer.Exit(1)
