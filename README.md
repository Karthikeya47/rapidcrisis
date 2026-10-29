# Rapid Crisis Response 🚨

**Say the emergency. The agent finds the right people and pages them in seconds.**

Rapid Crisis Response is a voice-first AI dispatch agent for hospitals. A nurse taps the mic and says
*"Need two trauma surgeons stat, Bay 4, patient coding."* An **NVIDIA Nemotron** agent running on
**Nebius Token Factory** understands the request, looks up the hospital protocol, finds on-shift staff
who are not already on another emergency, and pages them — showing every step it took.

Built for the **Nebius × NVIDIA Global AI Hackathon 2026** · Track: **Best Apps and Agents**

---

## The problem

In a hospital emergency, minutes decide outcomes. Today a nurse calls the switchboard, the operator
checks rosters and phones people one by one. Requests get lost, the wrong specialist is paged, or the
same surgeon is called to two emergencies at once.

## What it does

1. **Hear** — tap the mic and speak (browser speech recognition), or type.
2. **Understand** — Nemotron extracts the crisis type, location, urgency and who is needed.
3. **Look up protocol** — the agent calls the `lookup_protocol` tool (trauma, code blue, fire, respiratory, mass casualty, hazmat).
4. **Find staff** — the agent calls `find_available_staff` for each role. Staff already on an emergency are excluded, so **nobody is double-booked**.
5. **Complete the team** — if the protocol needs more roles than were asked for (e.g. trauma needs an anesthesiologist), the agent adds them, and the app warns if the full team can't be met.
6. **Never blocks** — if something important is missing (like the location), it dispatches anyway and asks one follow-up question.
7. **Page + log** — alerts appear on the staff phones live; every event goes to an audit log. Resolving an event frees the staff.

### Safety by design

- The model can **only dispatch people returned by the tools** — invented staff IDs are dropped.
- If the model is unreachable or returns bad output, a deterministic rule engine takes over, so the
  system **keeps working during an outage**. The UI shows which engine handled each request.

## Architecture

```
Browser (web dashboard)
  mic → Web Speech API → text
        │  POST /crisis
        ▼
FastAPI backend (Docker, Nebius AI Cloud)
  ┌──────────────────────────────────────────────────────────────┐
  │ Nemotron agent loop  (NVIDIA nemotron-3-super-120b-a12b,     │
  │                       Nebius Token Factory, OpenAI API)      │
  │   ├─ tool: lookup_protocol(crisis_type)                      │
  │   └─ tool: find_available_staff(role, count, excluding busy) │
  │ fallback: rule-based parser (no model needed)                │
  └──────────────────────────────────────────────────────────────┘
        │
        ├─ pager: alert → staff phones panel (live)
        ├─ availability: staff locked to event until resolved
        └─ audit log: JSONL
```

| Part | Tech |
| --- | --- |
| AI model | NVIDIA Nemotron 3 Super (`nvidia/nemotron-3-super-120b-a12b`) |
| Inference | Nebius Token Factory (OpenAI-compatible API, tool calling) |
| Backend | Python, FastAPI |
| Frontend | Single-page HTML/JS dashboard, Web Speech API |
| Hosting | Docker container on Nebius AI Cloud (Serverless endpoint) |
| Tests | pytest (52 tests, including the agent loop with a scripted model) |

## Run it locally

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # paste your NEBIUS_API_KEY (optional — runs on rules without it)
uvicorn main:app --reload --port 8080
```

Open http://localhost:8080 — use **Chrome or Edge** for voice input.

Run the tests:

```bash
cd backend
pip install pytest
pytest tests -q
```

## API

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/crisis` | `{"transcript": "...", "location_hint": "..."}` → run the agent and dispatch |
| GET | `/staff` | Roster with live status (`available` / `busy` / `off_shift`) |
| GET | `/staff/{id}/inbox` | Alerts received by one staff member |
| GET | `/events` | Recent emergencies |
| POST | `/events/{id}/resolve` | Close an emergency and free its staff |
| POST | `/reset` | Reset the demo |
| GET | `/health` | Status and which engine is active |

## Deploy on Nebius

See [DEPLOY.md](DEPLOY.md).

## What we built during the hackathon

This project started before the hackathon as a Google Cloud prototype (Flutter app + Gemini 1.5 Flash + BigQuery/Vertex AI).
That version no longer worked: Gemini 1.5 Flash was retired and the fallback path crashed. The original code is kept in
[`legacy/`](legacy/) for reference. During the hackathon we:

- **Replaced the AI brain** with NVIDIA Nemotron 3 Super on Nebius Token Factory, as a real multi-step tool-calling agent.
- **Fixed the crash** — rebuilt the offline fallback so the app never goes down if the model is unavailable.
- **Added no-double-booking** — staff are locked to an emergency until it is resolved.
- **Added protocol-aware team completion** and warnings when a full team isn't available.
- **Added follow-up questions** when key details (like location) are missing.
- **Built a new web dashboard** — voice input, live "agent at work" trace, staff phones panel, active emergencies.
- **Removed the Google Cloud dependency** so it runs anywhere as one Docker container, deployed on Nebius.
- **Rewrote and extended the tests** (52 passing), added CI and an MIT license.

## Limitations

- Uses a sample hospital roster and protocol library; a real deployment would connect to the hospital's shift and paging systems.
- Paging is shown in the dashboard's staff panel, not sent as real phone push notifications.
- This is a coordination aid, not a medical device; clinical decisions stay with clinicians.

## License

MIT — see [LICENSE](LICENSE).
