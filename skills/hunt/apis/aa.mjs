// Kayak and JetSMART over plain HTTP, through the api-anything ops in ./sites.
//
//   node aa.mjs install                                  copy ./sites/*.json into the api-anything home, sharing off
//   node aa.mjs kayak ORIG DEST DEPART RETURN|ow [adults 1|2|3|5]
//   node aa.mjs jetsmart DEP
//
// Prints one JSON object. Kayak prices are per person. A blocked Kayak call prints
// {ok:false, class:"blocked", ...}: run `npx --prefix <this dir> api-anything login kayak --window` once.
import { call } from "api-anything";
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const aaHome = process.env.API_ANYTHING_HOME || join(homedir(), ".api-anything");
const out = (o) => console.log(JSON.stringify(o));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const one = (d) => (Array.isArray(d) ? d[0] : d);

function install() {
  mkdirSync(join(aaHome, "sites"), { recursive: true });
  const copied = [];
  for (const f of readdirSync(join(here, "sites")).filter((f) => f.endsWith(".json"))) {
    copyFileSync(join(here, "sites", f), join(aaHome, "sites", f));
    copied.push(f);
  }
  // keep catalog sharing off unless the user turned it on themselves
  const settingsPath = join(aaHome, "settings.json");
  const settings = existsSync(settingsPath) ? JSON.parse(readFileSync(settingsPath, "utf8")) : {};
  if (settings.share === undefined) {
    writeFileSync(settingsPath, JSON.stringify({ ...settings, share: false, askedAt: new Date().toISOString() }, null, 2));
  }
  out({ ok: true, home: aaHome, copied, share: settings.share ?? false });
}

async function kayak(origin, destination, depart, ret, adultsArg) {
  const oneway = ret === "ow";
  const adults = Number(adultsArg ?? 1);
  if (oneway && adults !== 1) return out({ ok: false, class: "input", reason: "one-way is learned for 1 adult only" });
  if (!oneway && ![1, 2, 3, 5].includes(adults)) return out({ ok: false, class: "input", reason: "round trip is learned for 1, 2, 3 or 5 adults" });
  // poll/status were learned from a round trip; Kayak reads the search itself from searchId
  const args = { origin, destination, depart, return: oneway ? depart : ret };
  const startOp = oneway ? "startOneway" : adults === 1 ? "start" : `start${adults}`;
  const t0 = Date.now();
  const s = await call("kayak", startOp, oneway ? { origin, destination, depart } : args);
  if (!s.ok) return out({ ...s, op: startOp });
  const searchId = one(s.data)?.searchId;
  if (!searchId) return out({ ok: false, class: "drift", reason: "no searchId in start response" });
  let status = "first-phase";
  let searchUrl;
  for (let i = 0; i < 12 && status !== "complete"; i++) {
    await sleep(2500);
    const st = await call("kayak", "status", { ...args, searchId });
    if (!st.ok) return out({ ...st, op: "status" });
    status = one(st.data)?.status ?? status;
    searchUrl = one(st.data)?.searchUrl ?? searchUrl;
  }
  const p = await call("kayak", "poll", { ...args, searchId }, { maxChars: 200000 });
  if (!p.ok) return out({ ...p, op: "poll" });
  const rows = (p.data ?? []).filter((r) => r.type === "core").sort((a, b) => (a.price ?? 1e9) - (b.price ?? 1e9));
  out({ ok: true, origin, destination, depart, return: oneway ? null : ret, adults, searchId, searchUrl, status, ms: Date.now() - t0, rows });
}

async function jetsmart(dep) {
  const r = await call("jetsmart", "fares", { dep }, { maxChars: 200000 });
  out(r.ok ? { ok: true, dep, rows: r.data } : r);
}

const [cmd, ...rest] = process.argv.slice(2);
if (cmd === "install") install();
else if (cmd === "kayak" && rest.length >= 4) await kayak(...rest);
else if (cmd === "jetsmart" && rest.length >= 1) await jetsmart(rest[0]);
else {
  console.error("usage: node aa.mjs install | kayak ORIG DEST DEPART RETURN|ow [adults] | jetsmart DEP");
  process.exit(2);
}
