"""Check which flight-search tools work on this machine, and optionally install the missing ones.

  python doctor.py            check everything, including one live Google Flights search
  python doctor.py --quick    skip the live search
  python doctor.py --fix      also install what's missing: the fli CLI (uv tool) and Kayak/JetSMART
                              support (npm, into ~/.flight-hunter/apis, which survives plugin updates)

Ends with a card of the three levels: Base (Google Flights + Kiwi), Kayak, Chrome.
"""
import json
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flightapis as fa  # noqa: E402

FLI_SRC = "flights[mcp] @ git+https://github.com/punitarani/fli.git@881aee5ff4321e81ea2157cb44be94ce6a21dc1b"  # same pin as .mcp.json
UV_FIX = ('Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"   '
          "mac/linux: curl -LsSf https://astral.sh/uv/install.sh | sh")
ok = lambda m: print(f"  OK   {m}")
bad = lambda m, fix: print(f"  MISS {m}\n       fix: {fix}")
info = lambda m: print(f"  info {m}")


def run(cmd, timeout=120):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, "", str(e)


def node_version():
    node = shutil.which("node")
    if not node:
        return None
    code, out, _ = run([node, "--version"], timeout=20)
    try:
        return tuple(int(x) for x in out.strip().lstrip("v").split(".")[:2])
    except ValueError:
        return None


def check_base(quick, fix):
    print("Base: Google Flights (fli) + Kiwi")
    uv, git = shutil.which("uv"), shutil.which("git")
    ok(f"uv at {uv}") if uv else bad("uv (runs the fli and flight-apis MCP servers)", UV_FIX)
    ok("git") if git else bad("git (uv installs fli straight from GitHub)", "install git from https://git-scm.com")
    fli = shutil.which("fli")
    if not fli and fix and uv and git:
        print("  ...  installing the fli CLI (uv tool install)")
        code, out, err = run([uv, "tool", "install", "--force", FLI_SRC], timeout=600)
        fli = shutil.which("fli") or next((str(p) for p in (Path.home() / ".local" / "bin").glob("fli*")), None)
        if code:
            print("       " + (err or out)[-300:].replace("\n", " "))
    if fli:
        ok(f"fli CLI at {fli}")
    else:
        bad("fli CLI (saves searches as JSON; the MCP works without it)",
            f'uv tool install --force "{FLI_SRC}"   (PyPI "flights" is outdated: install from GitHub)')
    if fli and not quick:
        d = (date.today() + timedelta(days=45)).isoformat()
        code, out, err = run([fli, "flights", "JFK", "MIA", d, "--stops", "0", "--format", "json"])
        try:
            n = len(json.loads(out).get("flights", []))
            ok(f"fli live search works ({n} JFK-MIA results for {d})")
        except ValueError:
            bad("fli live search failed: " + (err or out)[-300:].replace("\n", " "),
                "reinstall from GitHub (command above). If Google changed its page, check "
                "https://github.com/punitarani/fli/issues and use Kiwi or the browser meanwhile")
    ok("Kiwi (remote MCP, nothing to install)")
    return bool(uv and git), bool(fli)


def check_kayak(fix):
    print("\nKayak level: Kayak + JetSMART over plain HTTP (optional)")
    v = node_version()
    if not v or v < (22, 13):
        bad(f"Node.js 22.13+ (found {'v%d.%d' % v if v else 'none'})", "install Node.js LTS from https://nodejs.org")
        return False, "Node.js 22.13+"
    ok(f"node v{v[0]}.{v[1]}")
    fa.sync_apis()
    if fa.needs_install() and fix:
        npm = shutil.which("npm")
        print(f"  ...  installing api-anything into {fa.APIS} (npm ci)")
        code, out, err = run([npm or "npm", "ci", "--prefix", str(fa.APIS), "--no-audit", "--no-fund"], timeout=600)
        if code:
            print("       " + (err or out)[-400:].replace("\n", " "))
        else:
            code, out, err = run([shutil.which("node"), str(fa.APIS / "aa.mjs"), "install"], timeout=60)
            if not code:
                fa.mark_installed()
    if fa.needs_install():
        bad(f"api-anything in {fa.APIS}", "run doctor.py --fix (or ask Claude to run the flight-hunter setup)")
        return False, "npm install (doctor.py --fix)"
    ok(f"api-anything installed in {fa.APIS}")
    specs = all((fa.AA_HOME / "sites" / f"{s}.json").exists() for s in ("kayak", "jetsmart"))
    if not specs:
        bad("Kayak + JetSMART specs", f'node "{fa.APIS / "aa.mjs"}" install')
        return False, "specs (doctor.py --fix)"
    ok("Kayak + JetSMART specs")
    ok("JetSMART fare cache (no login needed)")
    if not (fa.AA_HOME / "sessions" / "kayak.json").exists():
        bad("Kayak session (Kayak only answers requests carrying cookies a real browser got)",
            f"{fa.LOGIN_CMD}   (a window opens: load any Kayak search, clear a check if one shows, close it)")
        return False, "the one-time Kayak login window"
    ok("Kayak session")
    u = fa._usage()
    info(f"Kayak searches today: {u['count']}/{fa.KAYAK_DAILY} (budget shared by every tool)")
    return True, ""


def check_extras():
    print("\nExtras")
    try:
        import playwright  # noqa: F401
        ok("playwright: gf_multi.py can price Google multi-city trips")
    except ImportError:
        info("playwright isn't installed here; gf_multi.py (multi-city/open-jaw prices) pulls it in through "
             "`uv run --with playwright` and uses your installed Chrome")
    ok("Buquebus ferries (stdlib, no setup)")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    quick, fix = "--quick" in argv, "--fix" in argv
    print(f"flight-hunter doctor (python {sys.version.split()[0]}, state in {fa.HOME})\n")
    if sys.version_info < (3, 10):
        bad("Python 3.10+", "uv runs the scripts with a current Python: `uv run --no-project python ...`")
    base, fli_cli = check_base(quick, fix)
    kayak, kayak_need = check_kayak(fix)
    check_extras()
    print("\nLevels")
    print(f"  [{'ready' if base and fli_cli else 'partial' if base else 'missing':7}] Base    "
          "Google Flights (fli) + Kiwi" + ("" if base else "  <- install uv and git")
          + ("" if fli_cli or not base else "  <- fli CLI missing: MCP only (doctor.py --fix)"))
    print(f"  [{'ready' if kayak else 'missing':7}] Kayak   Kayak OTA fares at real group sizes, JetSMART"
          + ("" if kayak else f"  <- needs {kayak_need}"))
    print("  [  ?    ] Chrome  Skyscanner, airline sites, Kayak seller lists: Claude in Chrome extension, "
          "a Pro/Max/Team/Enterprise plan, and /chrome in Claude Code")
    print("\nAll levels are optional above Base. Without one, the hunt says which sources it skipped.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
