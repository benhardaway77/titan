import time
import typer
from rich import print

from titan.config.settings import Settings
from titan.promote import PromotePlan, run_promotion_checks

app = typer.Typer(no_args_is_help=True)


@app.command()
def run(env: str = typer.Option("paper", help="paper|live")):
    """Run Titan in paper or live mode (live is gated)."""
    settings = Settings.load(env)
    print(f"[bold]Titan[/bold] starting in env=[cyan]{settings.env}[/cyan]")
    if settings.env == "live" and not settings.live.enable_live:
        raise typer.BadParameter("Live env selected but enable_live=false. Refusing to run.")

    # Placeholder: wire pipeline
    print("Scaffold only: data -> signals -> risk -> portfolio -> broker -> report")

    # Keep the container alive (worker-style). When we implement the real pipeline,
    # this loop becomes the scheduler/event loop.
    while True:
        time.sleep(60)


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
