"""Skills management CLI commands."""

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()


@app.command("list")
def list_skills() -> None:
    """List all available analysis skills."""
    from sys_audit.skills import get_available_skills

    skills = get_available_skills()

    if not skills:
        console.print("[yellow]No skills available.[/yellow]")
        return

    table = Table(title="Available Skills")
    table.add_column("Name", style="cyan")
    table.add_column("Version")
    table.add_column("Description")
    table.add_column("Stakeholders")

    for skill in skills:
        table.add_row(
            skill.name,
            skill.version,
            skill.description,
            ", ".join(skill.stakeholders),
        )

    console.print(table)


@app.command("update")
def update_skills(
    channel: str = typer.Option(
        "stable", "--channel", "-c", help="Update channel: stable, latest, enterprise"
    ),
) -> None:
    """Update skill prompts from remote repository."""
    console.print(f"[yellow]Updating prompts from {channel} channel...[/yellow]")
    console.print("[dim]Not yet implemented - prompts are bundled with the current version.[/dim]")


@app.command("validate")
def validate_skills() -> None:
    """Validate skill configurations and prompts."""
    from sys_audit.skills import get_available_skills, validate_skill

    skills = get_available_skills()
    all_valid = True

    for skill in skills:
        issues = validate_skill(skill)
        if issues:
            all_valid = False
            console.print(f"[red]{skill.name}:[/red]")
            for issue in issues:
                console.print(f"  - {issue}")
        else:
            console.print(f"[green]{skill.name}:[/green] OK")

    if all_valid:
        console.print("\n[green]All skills validated successfully![/green]")
    else:
        console.print("\n[red]Some skills have issues.[/red]")
        raise typer.Exit(1)


@app.command("info")
def skill_info(
    name: str = typer.Argument(..., help="Skill name to show details for"),
) -> None:
    """Show detailed information about a skill."""
    from sys_audit.skills import get_skill_by_name

    skill = get_skill_by_name(name)

    if not skill:
        console.print(f"[red]Skill not found:[/red] {name}")
        raise typer.Exit(1)

    console.print(f"[bold cyan]{skill.name}[/bold cyan] v{skill.version}")
    console.print(f"\n{skill.description}")
    console.print(f"\n[bold]Stakeholders:[/bold] {', '.join(skill.stakeholders)}")

    if hasattr(skill, "static_tools") and skill.static_tools:
        console.print("\n[bold]Static Tools:[/bold]")
        for tool in skill.static_tools:
            console.print(f"  - {tool}")

    prompts = skill.get_prompts()
    if prompts:
        console.print(f"\n[bold]Prompts:[/bold] {len(prompts)} templates")
        for name in prompts:
            console.print(f"  - {name}")
