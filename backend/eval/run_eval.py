"""
run_eval.py — score dispatch engines on realistic spoken requests.

Each case in cases.jsonl is labelled with the right crisis type and location. An answer scores on:
  type      crisis type matches
  location  location matches (or, when none was said, the agent reports it as unknown)
  team      the paged team covers every role in the correct protocol's minimum team
  all       all three at once

Usage (from backend/):
  python eval/run_eval.py rules                                   # keyword rules, no model
  python eval/run_eval.py nvidia/nemotron-3-super-120b-a12b       # a Token Factory model (needs NEBIUS_API_KEY)
  python eval/run_eval.py --report                                # combine saved results into a Markdown table

Results are saved to eval/results/<engine>.json. Engines run sequentially within a process
because the staff roster is shared state; run engines in separate processes to parallelise.
"""
from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
BACKEND = HERE.parent
CASES = HERE / "cases.jsonl"
RESULTS = HERE / "results"

_NUMBERS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen".split())}


def load_cases(path: Path = CASES) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _norm(text: str) -> str:
    """Lower case, number words to digits ('ward six' -> 'ward 6'), punctuation to spaces."""
    words = re.sub(r"[^\w\s]", " ", str(text).lower()).split()
    return " ".join(_NUMBERS.get(w, w) for w in words)


def location_ok(predicted: str, expected: list[str] | None) -> bool:
    got = _norm(predicted or "unknown")
    if expected is None:  # nothing said: the honest answer is "unknown"
        return got in {"", "unknown", "not specified", "unspecified"} or "unknown" in got
    return any(re.search(rf"\b{re.escape(_norm(alt))}\b", got) for alt in expected)


def team_ok(roles: list[str], crisis_type: str) -> bool:
    from protocol_search import PROTOCOLS
    needed = PROTOCOLS[crisis_type]["staff_minimum"]
    return all(role in roles for role in needed)


def score(case: dict, crisis_type: str, location: str, roles: list[str]) -> dict:
    s = {"type": crisis_type == case["crisis_type"],
         "location": location_ok(location, case["location"]),
         "team": team_ok(roles, case["crisis_type"])}
    s["all"] = all(s.values())
    return s


def run(engine: str) -> dict:
    sys.path.insert(0, str(BACKEND))
    os.chdir(BACKEND)
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env")
    if engine == "rules":
        os.environ["NEBIUS_API_KEY"] = ""
    elif not os.getenv("NEBIUS_API_KEY"):
        sys.exit("NEBIUS_API_KEY is not set (backend/.env)")
    import agent
    from staff_finder import reset_availability
    if engine != "rules":
        agent.NEBIUS_MODEL = engine

    rows = []
    for case in load_cases():
        reset_availability()  # every case starts with the full roster
        t0 = time.time()
        ctx = agent.run_crisis_agent(case["transcript"])
        ms = int((time.time() - t0) * 1000)
        roles = [s.role for s in ctx.staff_list]
        rows.append({"id": case["id"], "group": case["group"], "ms": ms, "engine_used": ctx.engine,
                     "got_type": ctx.crisis_type, "got_location": ctx.location, "roles": roles,
                     **score(case, ctx.crisis_type, ctx.location, roles)})
        mark = "ok " if rows[-1]["all"] else "MISS"
        print(f"{mark} {case['id']:9} {ms:6d}ms {ctx.crisis_type:15} {ctx.location!r}", flush=True)

    RESULTS.mkdir(exist_ok=True)
    out = {"engine": engine, "rows": rows}
    (RESULTS / f"{engine.split('/')[-1]}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def summarise(result: dict) -> dict:
    rows = result["rows"]
    pct = lambda key: round(100 * sum(r[key] for r in rows) / len(rows))
    ms = sorted(r["ms"] for r in rows)
    return {"engine": result["engine"], "n": len(rows), "type": pct("type"), "location": pct("location"),
            "team": pct("team"), "all": pct("all"),
            "p50_s": round(statistics.median(ms) / 1000, 1), "max_s": round(ms[-1] / 1000, 1),
            "fallbacks": sum(r["engine_used"] == "rules" for r in rows) if result["engine"] != "rules" else 0,
            "by_group": {g: round(100 * sum(r["all"] for r in rows if r["group"] == g)
                                  / sum(1 for r in rows if r["group"] == g))
                         for g in dict.fromkeys(r["group"] for r in rows)}}


def report() -> str:
    order = ["rules", "NVIDIA-Nemotron-3-Nano-30B-A3B", "nemotron-3-super-120b-a12b", "Nemotron-3-Ultra-550b-a55b"]
    found = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in RESULTS.glob("*.json")}
    sums = [summarise(found[k]) for k in sorted(found, key=lambda k: order.index(k) if k in order else 99)]
    groups = list(sums[0]["by_group"]) if sums else []
    lines = ["| Engine | Fully right | Crisis type | Location | Full team | Median time | Slowest | Fell back to rules |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for s in sums:
        lines.append(f"| {s['engine']} | **{s['all']}%** | {s['type']}% | {s['location']}% | {s['team']}% "
                     f"| {s['p50_s']} s | {s['max_s']} s | {s['fallbacks']} of {s['n']} |")
    lines += ["", "Fully right, by kind of request:", "",
              "| Engine | " + " | ".join(groups) + " |", "| --- |" + " --- |" * len(groups)]
    for s in sums:
        lines.append(f"| {s['engine']} | " + " | ".join(f"{s['by_group'][g]}%" for g in groups) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    if sys.argv[1] == "--report":
        print(report())
    else:
        run(sys.argv[1])
