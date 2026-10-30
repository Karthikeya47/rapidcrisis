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
8. **Second opinion** - once the team is paged, **Nemotron 3 Ultra** reviews the dispatch against the whole hospital
   (other active emergencies, who is still free, who is off shift) and gives the charge nurse a risk level and up to four
   next actions. It runs in the background, so it never slows down paging.

### Why two models

Following the track's guidance (Ultra for serious reasoning, Nano or Super for fast everyday calls), we built an
evaluation set of **40 realistic spoken requests** ([`backend/eval/cases.jsonl`](backend/eval/cases.jsonl)): clean
requests, messy speech with no keywords, mid-sentence corrections, Hinglish, speech-recognition errors and requests
with no location. Each is labelled with the right crisis type and location. An answer is **fully right** only if the
crisis type and location are correct *and* the paged team covers every role in that crisis's protocol.

Results through Nebius Token Factory (same scores on two separate runs; times from the second run):

| Engine | Fully right | Crisis type | Location | Full team | Median time | Slowest |
| --- | --- | --- | --- | --- | --- | --- |
| Keyword rules (offline fallback) | **0%** | 58% | 60% | 0% | instant | instant |
| Nemotron 3 Nano | **15%** | 85% | 85% | 20% | 1.6 s | 2.8 s |
| Nemotron 3 Super | **85%** | 98% | 88% | 98% | 3.5 s | 6.6 s |
| Nemotron 3 Ultra | **90%** | 100% | 90% | 100% | 2.0 s | 17.4 s |

Fully right, by kind of request:

| Engine | Clean | No keywords | Correction | Hinglish | Speech errors | No location |
| --- | --- | --- | --- | --- | --- | --- |
| Keyword rules | 0% | 0% | 0% | 0% | 0% | 0% |
| Nemotron 3 Nano | 20% | 10% | 0% | 17% | 20% | 20% |
| Nemotron 3 Super | 100% | 80% | 100% | 83% | 40% | 100% |
| Nemotron 3 Ultra | 100% | 90% | 100% | 83% | 60% | 100% |

What we took from it:

- **Nano is not safe for paging**: it recognises the crisis but rarely pages the full protocol team.
- **Super dispatches.** It is right 85% of the time, and its slowest call (6.6 s) is predictable.
- **Ultra was the most accurate** (2 more cases out of 40, mostly garbled speech) and often fast, but its slowest call
  took 17 s, and in an emergency the worst case matters most. It is also the largest and most expensive model, so we use
  it where its reasoning pays off without anyone waiting: the **background review** of each dispatch, with reasoning on.
- Keyword rules got crisis type right on clean requests but never paged a full team: fine as an outage fallback, not as the brain.

Rerun it yourself (about 120 model calls, well under $1):

```bash
cd backend
python eval/run_eval.py rules
python eval/run_eval.py nvidia/nemotron-3-super-120b-a12b   # any Token Factory model id
python eval/run_eval.py --report
```

### Safety by design

- The model can **only dispatch people returned by the tools** — invented staff IDs are dropped.
- If the model is unreachable or returns bad output, a deterministic rule engine takes over, so the
  system **keeps working during an outage**. The UI shows which engine handled each request.
- **One request cannot empty the hospital**: a team is capped at the protocol's size plus two, with a warning.
- **Two emergencies never get the same person**, even when dispatched at the same moment: staff are claimed atomically.
- **Public-demo guards**: transcripts are capped at 500 characters, each device gets 5 dispatches a minute, and Ultra
  reviews have an hourly budget (dispatch keeps working when it runs out). All configurable in `.env`.

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
  ├──────────────────────────────────────────────────────────────┤
  │ background: Nemotron 3 Ultra review (Nemotron-3-Ultra-550b)  │
  │   whole-hospital capacity check -> risk + next actions       │
  │   served at GET /events/{id}/review                          │
  └──────────────────────────────────────────────────────────────┘
        │
        ├─ pager: alert → staff phones panel (live)
        ├─ availability: staff locked to event until resolved
        └─ audit log: JSONL
```

| Part | Tech |
| --- | --- |
| Dispatch model | NVIDIA Nemotron 3 Super (`nvidia/nemotron-3-super-120b-a12b`) |
| Review model | NVIDIA Nemotron 3 Ultra (`nvidia/Nemotron-3-Ultra-550b-a55b`) |
| Inference | Nebius Token Factory (OpenAI-compatible API, tool calling) |
| Backend | Python, FastAPI |
| Frontend | Single-page HTML/JS dashboard, Web Speech API |
| Hosting | Docker container on Nebius AI Cloud (Serverless endpoint) |
| Tests | pytest (74 tests, including the agent loop and the review with scripted models) |
| Evaluation | 40 labelled spoken requests scored across rules, Nano, Super and Ultra (`backend/eval`) |

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
| GET | `/events/{id}/review` | Nemotron Ultra's second opinion (`pending` / `done` / `failed` / `skipped` / `off`) |
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
- **Added a Nemotron 3 Ultra second opinion** that reviews every dispatch against hospital-wide capacity, in the background.
- **Rewrote and extended the tests** (74 passing), added CI and an MIT license.
- **Built a 40-case evaluation set** and measured every Nemotron size on it to choose models by data.

## Why a model and not keywords

The app ships with a keyword rule engine as an outage fallback, so we compared it with Nemotron 3 Super on
the messy sentences nurses actually say (these are the dashboard's example buttons):

| Spoken request | Nemotron 3 Super | Keyword rules |
| --- | --- | --- |
| "Kid in peds just swallowed a coin, he is turning blue" | Respiratory, Pediatrics, ICU doctor + nurse | Unknown crisis, one general doctor |
| "...one bleeding a lot, sorry not bay 4, put them in bay 6" | Trauma, **Bay 6**, full trauma team | Trauma, **Bay 4** (wrong bay), one surgeon |
| "Do mareez ICU mein, ek ka saans nahi chal raha" (Hinglish) | Respiratory, ICU, ICU doctor + nurse | Unknown crisis |
| "Smell of something burning near the oxygen store on floor 2" | Fire, critical, nurses + paramedics | Fire, one paramedic |

## Feedback on Nebius Token Factory and NVIDIA Nemotron

- **Token Factory was easy to adopt.** It is OpenAI-compatible, so the agent uses the standard `openai` SDK with a
  different base URL. Tool calling worked with Nemotron 3 Super on the first try, including several parallel tool calls
  in one reply, which let us dispatch in a single model call.
- **The model list was what we needed.** `GET /v1/models` exposed Nano, Super and Ultra under one key, so comparing the
  three on our own task took minutes and drove a measured model choice.
- **Turning reasoning off is essential for latency.** `chat_template_kwargs: {"enable_thinking": false}` was accepted and
  kept Super at 2-4 s per dispatch. A short note in the docs on which models support it would help.
- **Latency varies.** Most Super calls took 2.5-4.5 s, but we saw occasional 14 s calls. For an emergency use case a
  latency or priority tier would be valuable; we added a deterministic fallback so the app never waits indefinitely.
- **Model IDs use mixed casing** (`nemotron-3-super-120b-a12b` vs `Nemotron-3-Ultra-550b-a55b`), which is easy to get
  wrong when switching models by config.
- **Nemotron 3 Ultra gives genuinely useful reasoning** for the background review, for example noticing that no trauma
  surgeon would be left for a second trauma and suggesting an off-shift specialist by name.

## Limitations

- Uses a sample hospital roster and protocol library; a real deployment would connect to the hospital's shift and paging systems.
- Paging is shown in the dashboard's staff panel, not sent as real phone push notifications.
- This is a coordination aid, not a medical device; clinical decisions stay with clinicians.

## License

MIT — see [LICENSE](LICENSE).
