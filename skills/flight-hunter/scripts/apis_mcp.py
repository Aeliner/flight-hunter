"""MCP server (stdio, stdlib only) exposing the site APIs in flightapis.py and the trip watch as tools.

Registered by the plugin's .mcp.json as "flight-apis". Run by hand to debug:
  python apis_mcp.py        (speaks JSON-RPC on stdin/stdout)
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import flightapis as fa  # noqa: E402

DATE = {"type": "string", "description": "YYYY-MM-DD"}
IATA = {"type": "string", "description": "IATA airport or city code, e.g. MVD, GIG, NYC"}
TOOLS = [
    {"name": "kayak_search",
     "description": "Kayak fares over plain HTTP (no browser). Round trip for 1, 2, 3 or 5 adults, or one-way for "
                    "1 adult. Per-person USD prices, seller (airline or OTA), bags, times, link; cheapest first. "
                    "Takes ~10-25 s. Kayak blocks after heavy use: keep it to a few dozen searches a day.",
     "inputSchema": {"type": "object", "required": ["origin", "destination", "depart"], "properties": {
         "origin": IATA, "destination": IATA, "depart": DATE,
         "return": {**DATE, "description": "YYYY-MM-DD; omit for one-way"},
         "adults": {"type": "integer", "enum": [1, 2, 3, 5], "default": 1},
         "top": {"type": "integer", "default": 10}}}},
    {"name": "jetsmart_fares",
     "description": "JetSMART's cached lowest fare per flight (1 person, USD, base fare with carry-on only) from an "
                    "airport, for a date +/- days. One call covers 12 months; ~1-2 s.",
     "inputSchema": {"type": "object", "required": ["origin", "destination", "date"], "properties": {
         "origin": IATA, "destination": IATA, "date": DATE,
         "days": {"type": "integer", "default": 0, "description": "also show this many days either side"}}}},
    {"name": "buquebus_fares",
     "description": "Buquebus ferry fares (Montevideo/Colonia/Punta del Este <-> Buenos Aires): every sailing, seat "
                    "class and tariff, total USD for the adults. Ports: MVD, COL, PDE, BUE. ~5 s.",
     "inputSchema": {"type": "object", "required": ["origin", "destination", "date"], "properties": {
         "origin": {"type": "string"}, "destination": {"type": "string"}, "date": DATE,
         "adults": {"type": "integer", "default": 1}}}},
    {"name": "trip_watch",
     "description": "Re-price a trip file's finalists from APIs only (Kayak, fli, JetSMART, Buquebus) and diff "
                    "against the last run. Writes <workspace>/<today>/report.md, results.csv, summary.json. "
                    "Takes minutes (Kayak is paced). See references/watch.md for the trip file format.",
     "inputSchema": {"type": "object", "required": ["trip"], "properties": {
         "trip": {"type": "string", "description": "path to the trip JSON file"},
         "only": {"type": "string", "description": "comma list of finalist ids"},
         "no_kayak": {"type": "boolean", "default": False}}}},
]


def call_tool(name, a):
    if name == "kayak_search":
        return fa.kayak(a["origin"], a["destination"], a["depart"], a.get("return"), int(a.get("adults", 1)), int(a.get("top", 10)))
    if name == "jetsmart_fares":
        return fa.jetsmart(a["origin"], a["destination"], a["date"], int(a.get("days", 0)))
    if name == "buquebus_fares":
        return fa.ferry(a["origin"], a["destination"], a["date"], int(a.get("adults", 1)))
    if name == "trip_watch":
        cmd = [sys.executable, str(HERE / "watch.py"), a["trip"]]
        if a.get("only"):
            cmd += ["--only", a["only"]]
        if a.get("no_kayak"):
            cmd.append("--no-kayak")
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
        if p.returncode:
            raise fa.ApiError((p.stderr or p.stdout)[-800:])
        res = json.loads(p.stdout.strip().splitlines()[-1])
        res["report"] = (Path(res["out"]) / "report.md").read_text(encoding="utf-8")
        return res
    raise ValueError(f"unknown tool {name}")


def reply(id_, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": id_}
    msg.update({"error": error} if error else {"result": result})
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        method, id_ = msg.get("method"), msg.get("id")
        if id_ is None:  # notification (e.g. notifications/initialized)
            continue
        if method == "initialize":
            reply(id_, {"protocolVersion": msg.get("params", {}).get("protocolVersion", "2025-06-18"),
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "flight-apis", "version": "0.3.0"}})
        elif method == "tools/list":
            reply(id_, {"tools": TOOLS})
        elif method == "tools/call":
            p = msg.get("params", {})
            try:
                out = call_tool(p.get("name"), p.get("arguments") or {})
                reply(id_, {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}]})
            except fa.ApiBlocked as e:
                reply(id_, {"isError": True, "content": [{"type": "text", "text":
                      f"{e}\nKayak blocked this machine. Don't retry now. Ask the user to run once: "
                      f'npx --prefix "{fa.APIS}" api-anything login kayak --window   (load Kayak in the window, then close it). '
                      f"Meanwhile use fli / Kiwi, or Claude in Chrome."}]})
            except Exception as e:  # report tool failures to the model rather than killing the server
                reply(id_, {"isError": True, "content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}]})
        elif method == "ping":
            reply(id_, {})
        else:
            reply(id_, error={"code": -32601, "message": f"method not found: {method}"})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
