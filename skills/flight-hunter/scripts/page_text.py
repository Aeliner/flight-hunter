"""Load JS-heavy travel pages (Kayak, Skyscanner, airline sites) in your installed Chrome, headless,
and save the visible text - a fallback when the Claude in Chrome extension isn't connected.

  uv run --no-project --with playwright python page_text.py URL [URL ...] --out DIR [--wait 30] [--show]

Waits until the page text stops growing (results stream in), then saves <out>/<n>_<host>.txt and
prints the first lines. If the page shows a bot check / CAPTCHA, it reports BLOCKED and moves on -
never try to solve or bypass it; tell the user to check that site themselves.
"""
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

BOT = re.compile(r"captcha|are you a robot|not a robot|verify you are human|confirm you are human|"
                 r"unusual traffic|access denied|press (and|&) hold|bot detection|we need to make sure|"
                 r"thinks you are a .?bot|cannot grant you access|no pudimos permitir tu acceso", re.I)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--out", default=".")
    ap.add_argument("--wait", type=int, default=30, help="max seconds to wait for results")
    ap.add_argument("--show", action="store_true", help="visible browser instead of headless")
    ap.add_argument("--head", type=int, default=60, help="lines to print per page")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=not a.show)
        ctx = b.new_context(locale="en-US", viewport={"width": 1366, "height": 900})
        for i, url in enumerate(a.urls, 1):
            pg = ctx.new_page()
            host = urlparse(url).hostname or "page"
            print("=" * 20, url)
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:  # noqa: BLE001
                print("  LOAD FAILED:", str(e)[:200])
                pg.close()
                continue
            text, prev, stable = "", -1, 0
            for _ in range(max(1, a.wait // 3)):
                pg.wait_for_timeout(3000)
                text = pg.inner_text("body")
                if BOT.search(text[:3000]):
                    break
                stable = stable + 1 if len(text) == prev else 0
                if stable >= 2 and len(text) > 2000:
                    break
                prev = len(text)
            f = out / f"{i:02d}_{host}.txt"
            f.write_text(f"URL: {url}\n\n{text}", encoding="utf-8")
            if BOT.search(text[:3000]):
                print(f"  BLOCKED (bot check) - not bypassing. Saved {f}")
            else:
                lines = [l for l in text.splitlines() if l.strip()]
                print(f"  {len(text)} chars -> {f}")
                print("\n".join("  " + l[:160] for l in lines[:a.head]))
            pg.close()
        b.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
