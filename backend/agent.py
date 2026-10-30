"""
agent.py — the crisis agent's brain.

Primary brain: NVIDIA Nemotron 3 Super served by Nebius Token Factory
(OpenAI-compatible API). The model runs a real tool-calling loop:

    understand the request -> lookup_protocol -> find_available_staff -> decide

Every step is recorded in a trace so the UI can show the agent "thinking".

If no NEBIUS_API_KEY is set, or the model call fails, a deterministic
rule-based parser takes over so the app never goes down during a crisis.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from protocol_search import get_protocol, PROTOCOLS, ProtocolResult
from staff_finder import find_available_staff, ROLES, StaffMember

logger = logging.getLogger(__name__)

NEBIUS_BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
NEBIUS_MODEL = os.getenv("NEBIUS_MODEL", "nvidia/nemotron-3-super-120b-a12b")
MAX_AGENT_TURNS = 6

CRISIS_TYPES = list(PROTOCOLS.keys())

# ────────────────────────────────────────────────────────────
# Data classes
# ────────────────────────────────────────────────────────────
@dataclass
class CrisisIntent:
    crisis_type: str
    location: str
    staff_type: str
    count: int
    urgency: str
    summary: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CrisisContext:
    crisis_type: str
    location: str
    staff_type: str
    count: int
    urgency: str
    summary: str
    protocol: Optional[ProtocolResult]
    staff_list: list
    engine: str = "rules"                      # "nemotron" or "rules"
    follow_up: Optional[str] = None            # question the agent wants answered
    reasoning: str = ""
    trace: list = field(default_factory=list)  # step-by-step agent log for the UI


class Trace:
    """Collects the agent's steps with timings."""

    def __init__(self):
        self.steps: list[dict] = []
        self._t0 = time.time()

    def add(self, step: str, detail: str, source: str):
        self.steps.append({
            "step": step,
            "detail": detail,
            "source": source,
            "t_ms": int((time.time() - self._t0) * 1000),
        })


# ────────────────────────────────────────────────────────────
# Rule-based parser (offline fallback — never fails)
# ────────────────────────────────────────────────────────────
_NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "couple": 2,
}

_CRISIS_KEYWORDS = [
    ("mass_casualty", ["mass casualty", "multiple casualties", "many injured", "bus crash", "pile-up", "pileup", "explosion"]),
    ("chemical_spill", ["chemical", "spill", "hazmat", "toxic", "gas leak", "fumes"]),
    ("fire", ["fire", "smoke", "burning", "evacuate"]),
    ("cardiac_arrest", ["code blue", "cardiac", "heart attack", "arrest", "no pulse", "chest pain"]),
    ("respiratory", ["breath", "respiratory", "choking", "oxygen", "airway", "asthma", "desaturat"]),
    ("trauma", ["trauma", "bleeding", "gunshot", "stab", "accident", "fracture", "injur", "hemorrhag", "wound"]),
]

_ROLE_KEYWORDS = [
    ("anesthesiologist", ["anesthesiolog", "anaesthesiolog", "anesthetist"]),
    ("trauma_surgeon", ["surgeon"]),
    ("cardiologist", ["cardiologist"]),
    ("icu_doctor", ["icu doctor", "intensivist", "icu physician"]),
    ("paramedic", ["paramedic"]),
    ("nurse", ["nurse"]),
    ("general_doctor", ["doctor", "physician"]),
]

_DEFAULT_ROLE = {
    "trauma": "trauma_surgeon",
    "cardiac_arrest": "cardiologist",
    "fire": "paramedic",
    "respiratory": "icu_doctor",
    "mass_casualty": "trauma_surgeon",
    "chemical_spill": "paramedic",
    "unknown": "general_doctor",
}

_LOCATION_RE = re.compile(
    r"\b((?:bay|room|floor|ward|bed|wing|theatre|theater|block)\s*#?\s*[\w-]+"
    r"|(?:pediatric|paediatric|maternity|general|emergency|surgical)\s+ward"
    r"|emergency room|icu|er|ot|opd|lobby|parking(?:\s+lot)?)\b",
    re.IGNORECASE,
)


def _detect_count(text: str) -> int:
    staff_nouns = r"(?:surgeons?|nurses?|doctors?|physicians?|paramedics?|cardiologists?|anesthesiologists?|intensivists?|staff|people)"
    m = re.search(rf"\b(\d+|{'|'.join(_NUMBER_WORDS)})\s+(?:\w+\s+){{0,2}}?{staff_nouns}\b", text, re.IGNORECASE)
    if not m:
        return 1
    token = m.group(1).lower()
    n = int(token) if token.isdigit() else _NUMBER_WORDS.get(token, 1)
    return max(1, min(n, 10))


def _detect_location(text: str) -> str:
    m = _LOCATION_RE.search(text)
    if not m:
        return "unknown"
    loc = m.group(1).strip()
    return loc.upper() if loc.lower() in {"icu", "er", "ot", "opd"} else loc.title()


def _mock_parse(transcript: str) -> CrisisIntent:
    text = transcript.lower()

    crisis_type = "unknown"
    for ctype, words in _CRISIS_KEYWORDS:
        if any(w in text for w in words):
            crisis_type = ctype
            break

    staff_type = None
    for role, words in _ROLE_KEYWORDS:
        if any(w in text for w in words):
            staff_type = role
            break
    if crisis_type == "unknown" and staff_type == "trauma_surgeon":
        crisis_type = "trauma"
    staff_type = staff_type or _DEFAULT_ROLE[crisis_type]

    if crisis_type in {"trauma", "cardiac_arrest", "fire", "mass_casualty", "chemical_spill"} \
            or re.search(r"\b(stat|immediately|now|coding|urgent|asap)\b", text):
        urgency = "critical"
    elif crisis_type == "respiratory":
        urgency = "high"
    else:
        urgency = "medium"

    return CrisisIntent(
        crisis_type=crisis_type,
        location=_detect_location(transcript),
        staff_type=staff_type,
        count=_detect_count(transcript),
        urgency=urgency,
        summary=transcript.strip()[:200],
    )


def parse_crisis_intent(transcript: str) -> CrisisIntent:
    """Quick intent parse (rules). Kept for backwards compatibility and tests."""
    return _mock_parse(transcript)


# ────────────────────────────────────────────────────────────
# Nemotron tool-calling agent
# ────────────────────────────────────────────────────────────
_TEAM_TABLE = "\n".join(
    f"- {k}: {', '.join(f'{n} {r}' for r, n in v['staff_minimum'].items())}" for k, v in PROTOCOLS.items()
)

SYSTEM_PROMPT = f"""You are the dispatch agent of a hospital crisis-response system.
A staff member has spoken a short emergency request (voice transcript, may contain errors).
Speed matters: lives depend on it. Do NOT deliberate at length.

In ONE single reply, call ALL of these tools in parallel:
  - report_crisis: your reading of the request (type, location, urgency, alert text, follow-up question)
  - lookup_protocol: the protocol for that crisis type
  - find_available_staff: once for EACH role needed (the role the speaker asked for, with their
    count, plus any other roles in the protocol's minimum team below)

Minimum team per crisis type:
{_TEAM_TABLE}

Valid roles: {", ".join(ROLES)}
Never block on missing information: if something important is missing (e.g. no location),
set follow_up_question to ONE short question; otherwise set it to an empty string."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "report_crisis",
            "description": "Record your understanding of the emergency.",
            "parameters": {
                "type": "object",
                "properties": {
                    "crisis_type": {"type": "string", "enum": CRISIS_TYPES},
                    "location": {"type": "string", "description": "where, or 'unknown'"},
                    "urgency": {"type": "string", "enum": ["critical", "high", "medium"]},
                    "primary_role": {"type": "string", "enum": ROLES},
                    "count": {"type": "integer", "minimum": 1, "maximum": 10},
                    "summary": {"type": "string", "description": "one-line alert for staff phones"},
                    "follow_up_question": {"type": "string"},
                    "reasoning": {"type": "string", "description": "one short sentence: why this team"},
                },
                "required": ["crisis_type", "location", "urgency", "primary_role", "count", "summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_protocol",
            "description": "Get the hospital protocol (steps and minimum team) for a crisis type.",
            "parameters": {
                "type": "object",
                "properties": {"crisis_type": {"type": "string", "enum": CRISIS_TYPES}},
                "required": ["crisis_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_available_staff",
            "description": "Find on-shift staff of a role who are NOT already assigned to another emergency.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "enum": ROLES},
                    "count": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["role", "count"],
            },
        },
    },
]

FINAL_JSON_HINT = """If you have everything, reply with ONLY this JSON (no markdown):
{"crisis_type": "...", "location": "...", "urgency": "critical|high|medium", "primary_role": "...",
 "count": 1, "summary": "...", "staff_ids": ["..."], "follow_up_question": "", "reasoning": "..."}"""


def _parse_json(text: str) -> dict:
    """Extract the first JSON object from model output (tolerates fences / extra prose)."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in model output: {text[:200]!r}")
    return json.loads(text[start:end + 1])


_client = None


def _make_client():
    """One shared client: reuses the HTTPS connection to Token Factory between requests."""
    global _client
    if _client is None:
        _client = _new_client()
    return _client


def _new_client():
    from openai import OpenAI
    return OpenAI(base_url=NEBIUS_BASE_URL, api_key=os.environ["NEBIUS_API_KEY"],
                  timeout=float(os.getenv("NEBIUS_TIMEOUT", "25")), max_retries=0)


# Reasoning ("thinking") makes Nemotron much slower. We ask the server to switch it off;
# if this server doesn't accept the option we remember that and stop sending it.
_THINKING_OFF = {"chat_template_kwargs": {"enable_thinking": False}}
_thinking_flag_ok = os.getenv("NEBIUS_DISABLE_THINKING", "1") == "1"


def _chat(client, messages):
    global _thinking_flag_ok
    kwargs = dict(model=NEBIUS_MODEL, messages=messages, tools=TOOLS, tool_choice="auto",
                  temperature=0.1, max_tokens=1200)
    if _thinking_flag_ok:
        try:
            return client.chat.completions.create(**kwargs, extra_body=_THINKING_OFF)
        except Exception as e:  # server rejected the option -> retry plain
            if getattr(e, "status_code", None) in (400, 422):
                logger.warning(f"Server rejected thinking toggle, retrying without it: {e}")
                _thinking_flag_ok = False
            else:
                raise
    return client.chat.completions.create(**kwargs)


def _run_nemotron_agent(transcript: str, location_hint: Optional[str], trace: Trace,
                        client=None) -> CrisisContext:
    client = client or _make_client()
    user_msg = f"Transcript: \"{transcript}\""
    if location_hint:
        user_msg += f"\nLocation reported by the device: {location_hint}"
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    protocol: Optional[ProtocolResult] = None
    found: dict[str, StaffMember] = {}
    report: Optional[dict] = None
    data: Optional[dict] = None
    model_calls = 0

    for _turn in range(MAX_AGENT_TURNS):
        t0 = time.time()
        resp = _chat(client, messages)
        model_calls += 1
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []
        trace.add("Nemotron", f"model call {model_calls}: {len(tool_calls)} tool call(s) in "
                              f"{time.time() - t0:.1f}s", f"NVIDIA {NEBIUS_MODEL.split('/')[-1]}")

        if not tool_calls:
            data = _parse_json(msg.content)
            break

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ],
        })
        for tc in tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            if tc.function.name == "report_crisis":
                report = args
                result = {"ok": True}
                trace.add("Understand", f"{args.get('crisis_type')}, {args.get('urgency')}, at "
                                        f"{args.get('location')}", "tool: report_crisis")
            elif tc.function.name == "lookup_protocol":
                protocol = get_protocol(args.get("crisis_type", "unknown"), transcript)
                result = {"name": protocol.name, "code": protocol.code,
                          "steps": protocol.steps, "staff_minimum": protocol.staff_minimum}
                trace.add("Protocol", f"{protocol.code} {protocol.name}", "tool: lookup_protocol")
            elif tc.function.name == "find_available_staff":
                role, count = args.get("role", "general_doctor"), int(args.get("count", 1) or 1)
                staff = find_available_staff(role, count, exclude=set(found))
                for s in staff:
                    found[s.staff_id] = s
                result = {"role": role, "requested": count,
                          "available": [s.public_dict() for s in staff]}
                names = ", ".join(s.name for s in staff) or "none free"
                trace.add("Staff search", f"{count} x {role}: {names}", "tool: find_available_staff")
            else:
                result = {"error": f"unknown tool {tc.function.name}"}
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})

        # Fast path: the model already told us everything in one reply — no second model call.
        if report is not None and any(tc.function.name == "find_available_staff" for tc in tool_calls):
            data = dict(report, staff_ids=list(found))
            break
        if _turn == 0:
            messages.append({"role": "user", "content": FINAL_JSON_HINT})
    else:
        raise RuntimeError("Agent did not finish within the turn limit")

    crisis_type = data.get("crisis_type") if data.get("crisis_type") in PROTOCOLS else "unknown"
    if protocol is None:
        protocol = get_protocol(crisis_type, transcript)
        trace.add("Protocol", f"{protocol.code} {protocol.name}", "rules (model skipped tool)")

    # Only dispatch staff the tools actually returned — the model cannot invent people.
    chosen = [found[i] for i in data.get("staff_ids", []) if i in found]
    if not chosen:
        chosen = list(found.values())
    if not chosen:
        chosen = find_available_staff(data.get("primary_role", "general_doctor"), int(data.get("count", 1) or 1))

    location = str(data.get("location") or "unknown")
    if location.lower() == "unknown" and location_hint:
        location = location_hint
    follow_up = data.get("follow_up_question")
    if not isinstance(follow_up, str) or follow_up.strip().lower() in {"", "null", "none"}:
        follow_up = None

    return CrisisContext(
        crisis_type=crisis_type,
        location=location,
        staff_type=data.get("primary_role", "general_doctor"),
        count=int(data.get("count", 1) or 1),
        urgency=data.get("urgency", "high") if data.get("urgency") in {"critical", "high", "medium"} else "high",
        summary=data.get("summary") or transcript,
        protocol=protocol,
        staff_list=chosen,
        engine="nemotron",
        follow_up=follow_up,
        reasoning=data.get("reasoning", ""),
        trace=trace.steps,
    )


def _rules_agent(transcript: str, location_hint: Optional[str], trace: Trace) -> CrisisContext:
    intent = _mock_parse(transcript)
    if intent.location == "unknown" and location_hint:
        intent.location = location_hint
    trace.add("Understand", f"{intent.crisis_type}, {intent.urgency}, at {intent.location}", "rules")

    protocol = get_protocol(intent.crisis_type, intent.summary)
    trace.add("Protocol", f"{protocol.code} {protocol.name}", "rules")

    staff = find_available_staff(intent.staff_type, intent.count)
    names = ", ".join(s.name for s in staff) or "none free"
    trace.add("Staff search", f"{intent.count} x {intent.staff_type}: {names}", "rules")

    follow_up = "Where exactly is the emergency?" if intent.location == "unknown" else None
    return CrisisContext(
        crisis_type=intent.crisis_type, location=intent.location, staff_type=intent.staff_type,
        count=intent.count, urgency=intent.urgency, summary=intent.summary,
        protocol=protocol, staff_list=staff, engine="rules", follow_up=follow_up,
        reasoning="Offline keyword rules (no model available).", trace=trace.steps,
    )


def nemotron_enabled() -> bool:
    return bool(os.getenv("NEBIUS_API_KEY"))


def run_crisis_agent(transcript: str, location_hint: str = None, client=None) -> CrisisContext:
    """Run the agent. Uses Nemotron when configured; falls back to rules on any failure."""
    trace = Trace()
    trace.add("Heard", transcript, "voice / text input")

    if nemotron_enabled() or client is not None:
        try:
            return _run_nemotron_agent(transcript, location_hint, trace, client=client)
        except Exception as e:
            logger.error(f"Nemotron agent failed, using rules fallback: {e}")
            trace.add("Fallback", f"Model unavailable ({type(e).__name__}); switched to offline rules", "safety net")

    return _rules_agent(transcript, location_hint, trace)
