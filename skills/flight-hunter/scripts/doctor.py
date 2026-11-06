"""Check which flight-search tools are available on this machine and print how to fix gaps.

Usage: python doctor.py [--quick]   (--quick skips the live fli test search)
"""
import json
import shutil
import subprocess
import sys
from datetime import date, timedelta

FLI_SRC = "flights[mcp] @ git+https://github.com/punitarani/fli.git"
ok = lambda m: print(f"  OK   {m}")
bad = lambda m, fix: print(f"  MISS {m}\n       fix: {fix}")


def run(cmd, timeout=120):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, "", str(e)


def main():
    quick = "--quick" in sys.argv
    print("flight-hunter doctor")
    print(f"  OK   python {sys.version.split()[0]}")

    uv = shutil.which("uv")
    ok(f"uv at {uv}") if uv else bad("uv (needed to install fli)",
                                    "Windows: powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"; "
                                    "mac/linux: curl -LsSf https://astral.sh/uv/install.sh | sh")
    if not shutil.which("git"):
        bad("git (uv installs fli straight from GitHub)", "install git, then rerun")

    fli = shutil.which("fli")
    if fli:
        ok(f"fli CLI at {fli}")
    else:
        bad("fli CLI", f'uv tool install --force "{FLI_SRC}"   '
                       "(PyPI 'flights' is outdated - always install from GitHub)")
    if fli and not quick:
        d = (date.today() + timedelta(days=45)).isoformat()
        code, out, err = run([fli, "flights", "JFK", "MIA", d, "--stops", "0", "--format", "json"])
        try:
            n = len(json.loads(out).get("flights", []))
            ok(f"fli live search works ({n} JFK-MIA results for {d})")
        except ValueError:
            bad("fli live search failed: " + (err or out)[-300:].replace("\n", " "),
                "reinstall from GitHub (command above); if Google changed its page, check "
                "https://github.com/punitarani/fli/issues and fall back to fast-flights or the browser")

    for name in ("fli-mcp",):
        ok(f"{name} on PATH") if shutil.which(name) else print(
            f"  info {name} not on PATH (fine if the flight-hunter plugin is installed: it launches fli-mcp via uvx)")

    try:
        import playwright  # noqa: F401
        ok("playwright (python) importable - gf_multi.py can scrape Google multi-city")
    except ImportError:
        print("  info playwright not installed - only needed for gf_multi.py (multi-city/open-jaw prices). "
              "run it via: uv run --no-project --with fast-flights --with typing_extensions --with playwright python gf_multi.py ... (uses your installed Chrome, no browser download)")

    print("\nBrowser cross-checks (Kayak, Skyscanner, airline sites) need the Claude in Chrome extension "
          "connected; without it rely on fli + Kiwi MCP and give the user links to check.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
