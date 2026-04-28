"""
agent.py — Gemini 1.5 Flash brain for Rapid Crisis Response
Uses Function Calling to orchestrate protocol lookup and staff finding.
"""
import json
import os
import re
import logging
from dataclasses import dataclass
from typing import Optional, Any

from google import genai
from google.genai import types as genai_types

# Import tools for Gemini to call
from protocol_search import get_protocol
from staff_finder import find_available_staff

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-1.5-flash"

SYSTEM_PROMPT = """
You are a medical emergency coordination AI.
Your goal is to handle a crisis request by:
1. Parsing the user's voice transcript.
2. Finding the correct medical protocol.
3. Finding available staff to dispatch.

You have tools to:
- get_protocol: Retrieves the hospital protocol for a specific crisis type.
- find_available_staff: Searches for on-shift staff (surgeons, nurses, etc.) in BigQuery/Cloud SQL.

Workflow:
- Always call `get_protocol` based on the detected crisis.
- Always call `find_available_staff` based on the protocol requirements or user request.
- After receiving tool outputs, provide a final structured response.

Final response MUST be a JSON object with:
{
  "crisis_type": "...",
  "location": "...",
  "staff_type": "...",
  "count": 2,
  "urgency": "critical|high|medium",
  "summary": "...",
  "protocol_code": "...",
  "staff_ids": ["S001", "S002"]
}
"""

@dataclass
class CrisisContext:
    crisis_type: str
    location: str
    staff_type: str
    count: int
    urgency: str
    summary: str
    protocol: Any
    staff_list: list

def _parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\n?", "", text.strip())
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text)

def run_crisis_agent(transcript: str, location_hint: str = None) -> CrisisContext:
    """
    Executes the agentic pipeline using Gemini 1.5 Flash with Function Calling.
    Orchestrates THINK -> FIND PROTOCOL -> FIND STAFF in a single multi-turn interaction.
    """
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GENAI_API_KEY")
    if not api_key:
        logger.warning("No API key — falling back to mock agent logic")
        return _mock_agent_fallback(transcript, location_hint)

    client = genai.Client(api_key=api_key)

    # Define the tools
    tools = [get_protocol, find_available_staff]

    # Start chat session for multi-turn function calling
    chat = client.chats.create(
        model=GEMINI_MODEL,
        config=genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=tools,
            temperature=0.1,
        )
    )

    try:
        # Initial prompt
        prompt = f"Crisis Request: '{transcript}'"
        if location_hint:
            prompt += f" | Location Hint: {location_hint}"

        response = chat.send_message(prompt)

        # Gemini handles the tool calls automatically if using the high-level Chat SDK
        # but we need to ensure it reached a final answer.

        raw_text = response.text
        logger.info(f"Agent Final Response: {raw_text}")

        data = _parse_json(raw_text)

        # We still need the actual objects for the rest of the pipeline
        # Since Gemini just returned IDs/Codes, we fetch the full objects one last time
        # Or better: Gemini could have returned them if the tools were structured that way.

        protocol = get_protocol(data.get("crisis_type", "unknown"), data.get("summary", ""))
        staff = find_available_staff(data.get("staff_type", "general_doctor"), data.get("count", 1))

        return CrisisContext(
            crisis_type=data.get("crisis_type", "unknown"),
            location=data.get("location", "unknown"),
            staff_type=data.get("staff_type", "general_doctor"),
            count=int(data.get("count", 1)),
            urgency=data.get("urgency", "high"),
            summary=data.get("summary", transcript),
            protocol=protocol,
            staff_list=staff
        )

    except Exception as e:
        logger.error(f"Agent Pipeline Error: {e}")
        return _mock_agent_fallback(transcript, location_hint)

def _mock_agent_fallback(transcript: str, location_hint: str) -> CrisisContext:
    # Basic logic for when Gemini/Network is down
    from agent import _mock_parse  # Reuse the old mock parser
    intent = _mock_parse(transcript)
    if location_hint and intent.location == "unknown":
        intent.location = location_hint

    protocol = get_protocol(intent.crisis_type, intent.summary)
    staff = find_available_staff(intent.staff_type, intent.count)

    return CrisisContext(
        crisis_type=intent.crisis_type,
        location=intent.location,
        staff_type=intent.staff_type,
        count=intent.count,
        urgency=intent.urgency,
        summary=intent.summary,
        protocol=protocol,
        staff_list=staff
    )
