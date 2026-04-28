"""
agent.py — Gemini 1.5 Flash brain for Rapid Crisis Response
Parses voice transcript → structured crisis intent JSON
"""
import json
import os
import re
import logging
from dataclasses import dataclass
from typing import Optional

from google import genai
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-1.5-flash"

SYSTEM_PROMPT = """
You are a medical emergency coordination AI in a hospital crisis system.
Your job is to parse a voice command from hospital staff and extract structured crisis information.

Extract the following fields:
- crisis_type: one of [trauma, cardiac_arrest, fire, code_blue, chemical_spill, mass_casualty, respiratory, unknown]
- location: the physical location mentioned (bay number, floor, room, ward name)
- staff_type: the PRIMARY type of staff needed [trauma_surgeon, cardiologist, nurse, icu_doctor, anesthesiologist, paramedic, general_doctor]
- count: number of staff needed (integer, default 1 if not specified)
- urgency: one of [critical, high, medium] based on the crisis type and language tone
- summary: a short 1-sentence summary of the request

Always respond with ONLY valid JSON. No explanation. No markdown. Just raw JSON.

Example input: "Need two trauma surgeons stat, Bay 4, patient coding"
Example output:
{
  "crisis_type": "trauma",
  "location": "Bay 4",
  "staff_type": "trauma_surgeon",
  "count": 2,
  "urgency": "critical",
  "summary": "2 trauma surgeons urgently needed at Bay 4 for coding patient"
}
"""


@dataclass
class CrisisIntent:
    crisis_type: str
    location: str
    staff_type: str
    count: int
    urgency: str
    summary: str

    def to_dict(self) -> dict:
        return {
            "crisis_type": self.crisis_type,
            "location": self.location,
            "staff_type": self.staff_type,
            "count": self.count,
            "urgency": self.urgency,
            "summary": self.summary,
        }


def _parse_json_from_response(text: str) -> dict:
    """Extract JSON from Gemini response, stripping any markdown fences."""
    text = text.strip()
    # Remove markdown code fences if present
    text = re.sub(r"^```(?:json)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text.strip())


def parse_crisis_intent(transcript: str) -> CrisisIntent:
    """
    Send transcript to Gemini 1.5 Flash and extract structured crisis intent.
    Falls back to a safe default on any error.
    """
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GENAI_API_KEY")
    
    if not api_key:
        logger.warning("No Gemini API key found — using mock intent extraction")
        return _mock_parse(transcript)

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=transcript,
            config=genai_types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.1,
                max_output_tokens=512,
            ),
        )
        raw = response.text
        logger.info(f"Gemini raw response: {raw}")
        data = _parse_json_from_response(raw)
        return CrisisIntent(
            crisis_type=data.get("crisis_type", "unknown"),
            location=data.get("location", "unknown"),
            staff_type=data.get("staff_type", "general_doctor"),
            count=int(data.get("count", 1)),
            urgency=data.get("urgency", "high"),
            summary=data.get("summary", transcript),
        )
    except Exception as e:
        logger.error(f"Gemini parse error: {e}")
        return _mock_parse(transcript)


def _mock_parse(transcript: str) -> CrisisIntent:
    """Rule-based fallback when Gemini is unavailable."""
    t = transcript.lower()
    crisis_type = "unknown"
    staff_type = "general_doctor"
    urgency = "high"
    count = 1

    if "trauma" in t:
        crisis_type = "trauma"
        staff_type = "trauma_surgeon"
        urgency = "critical"
    elif "cardiac" in t or "heart" in t or "code blue" in t:
        crisis_type = "cardiac_arrest"
        staff_type = "cardiologist"
        urgency = "critical"
    elif "fire" in t:
        crisis_type = "fire"
        staff_type = "paramedic"
        urgency = "critical"
    elif "respiratory" in t or "breathing" in t:
        crisis_type = "respiratory"
        staff_type = "icu_doctor"
        urgency = "high"
    elif "nurse" in t:
        staff_type = "nurse"
    elif "anesthes" in t:
        staff_type = "anesthesiologist"

    # Extract count hints
    for word, num in [("two", 2), ("three", 3), ("four", 4), ("five", 5), ("2", 2), ("3", 3)]:
        if word in t:
            count = num
            break

    return CrisisIntent(
        crisis_type=crisis_type,
        location="unknown",
        staff_type=staff_type,
        count=count,
        urgency=urgency,
        summary=f"[Mock] Crisis detected: {crisis_type} — {staff_type} x{count}",
    )
