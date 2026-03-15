import logging

import typer
from rich import print

from titan.config.settings import Settings
from titan.promote import PromotePlan, run_promotion_checks

app = typer.Typer(no_args_is_help=True)


@app.command()
def run(env: str = typer.Option("paper", help="paper|live")):
    """Run Titan in paper or live mode (live is gated)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = Settings.load(env)
    print(f"[bold]Titan[/bold] starting in env=[cyan]{settings.env}[/cyan]")

    if settings.env == "live" and not settings.live.enable_live:
        raise typer.BadParameter("Live env selected but enable_live=false. Refusing to run.")

    # Deferred import: keeps `titan promote` fast (never instantiates agents)
    from titan.agent import run_agents

    try:
        run_agents(settings)
    except KeyboardInterrupt:
        print("\n[bold yellow]Titan stopped.[/bold yellow]")


@app.command()
def promote(
    from_env: str = typer.Option("paper", help="Source env"),
    to_env: str = typer.Option("live", help="Target env"),
):
    """Run promotion checks (paper -> live) before you merge/deploy."""
    code = run_promotion_checks(PromotePlan(from_env=from_env, to_env=to_env))
    raise typer.Exit(code=code)


if __name__ == "__main__":
    app()
