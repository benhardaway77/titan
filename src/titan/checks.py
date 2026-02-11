from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str = ""


def _run(cmd: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
        out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
        return (p.returncode == 0), out.strip()
    except Exception as e:
        return False, str(e)


def run_unit_tests(repo_root: Path) -> CheckResult:
    # Prefer pytest if installed; fallback to unittest discovery.
    pytest = _which("pytest")
    if pytest:
        ok, out = _run([pytest, "-q"], cwd=repo_root)
        return CheckResult("unit_tests(pytest)", ok, out)

    ok, out = _run(["python3", "-m", "unittest", "discover", "-s", "tests"], cwd=repo_root)
    return CheckResult("unit_tests(unittest)", ok, out)


def require_live_gate() -> CheckResult:
    # Live must remain disabled unless explicitly enabled.
    v = (os.getenv("TITAN_ENABLE_LIVE") or "false").strip().lower()
    ok = v in ("false", "0", "no", "off", "")
    return CheckResult("live_gate_disabled", ok, f"TITAN_ENABLE_LIVE={v}")


def _which(name: str) -> str | None:
    from shutil import which

    return which(name)
