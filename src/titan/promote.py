from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from titan.checks import require_live_gate, run_unit_tests


@dataclass
class PromotePlan:
    from_env: str = "paper"
    to_env: str = "live"


def run_promotion_checks(plan: PromotePlan) -> int:
    console = Console()
    repo_root = Path(__file__).resolve().parents[3]

    checks = [
        require_live_gate(),
        run_unit_tests(repo_root),
    ]

    ok_all = True
    console.print(f"[bold]Promotion checks[/bold] {plan.from_env} -> {plan.to_env}")
    for c in checks:
        status = "[green]PASS[/green]" if c.ok else "[red]FAIL[/red]"
        console.print(f"- {status} {c.name}")
        if not c.ok:
            ok_all = False
            if c.details:
                console.print(f"  [dim]{c.details}[/dim]")

    if not ok_all:
        console.print("\n[red]Promotion blocked.[/red]")
        return 2

    console.print("\n[green]Promotion checks passed.[/green] (No automatic merge/deploy performed.)")
    return 0
