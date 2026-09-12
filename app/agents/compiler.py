"""Compiler agent: synthesizes all data into human-readable itinerary."""

import json
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import GEMINI_API_KEY, MAX_RETRIES
from app.exceptions import LLMError
from app.schemas import PlannerState, ItineraryResponse, DayPlan
from .llm_utils import call_llm


def build_prompt(state: PlannerState) -> str:
    """Build a rich prompt for itinerary synthesis."""
    constraints = state["constraints"]
    pois_per_day = {cluster.day_number: cluster.pois for cluster in state["day_clusters"]}
    lodging = state["lodging"][0] if state["lodging"] else None
    transit = state["transit"][0] if state["transit"] else None

    prompt = f"""Create a detailed {constraints.n_days}-day travel itinerary for {constraints.destination}.

Trip Details:
- Destination: {constraints.destination}
- Duration: {constraints.n_days} days
- Budget Level: {constraints.budget}
- Travellers: {constraints.traveller_count}
- Interests: {', '.join(constraints.interests) if constraints.interests else 'general sightseeing'}

Accommodation:
{f"- {lodging.name} ({lodging.type})" if lodging else "- To be arranged"}

Daily POIs to include:
"""

    for day_num in range(1, constraints.n_days + 1):
        pois = pois_per_day.get(day_num, [])
        prompt += f"\nDay {day_num}:\n"
        for poi in pois:
            prompt += f"  - {poi.name} ({poi.category}): {poi.description}\n"

    prompt += """
Return a JSON object with the following structure:
{
  "days": [
    {
      "day_number": 1,
      "theme": "Iconic Landmarks",
      "narrative": "Start your journey with the city's most iconic landmarks...",
      "estimated_walking_km": 5.2
    }
  ],
  "tips": ["Tip 1", "Tip 2"],
  "total_estimated_cost": 1500
}

Make the narrative engaging and practical. Include time estimates and logistics tips."""

    return prompt


def parse_llm_output(raw: str) -> ItineraryResponse:
    """Parse LLM output into ItineraryResponse."""
    json_start = raw.find("{")
    json_end = raw.rfind("}") + 1

    if json_start == -1 or json_end == 0:
        raise ValueError("No JSON found in LLM output")

    json_str = raw[json_start:json_end]
    parsed = json.loads(json_str)

    return parsed


def compile_itinerary(state: PlannerState) -> PlannerState:
    """
    Compiler agent node: synthesize final itinerary.

    Args:
        state: Current PlannerState

    Returns:
        Updated PlannerState with compiled itinerary
    """
    # Safety check
    if state["constraints"] is None:
        state["status"] = "error"
        state["validation_errors"].append("No constraints available for compilation")
        return state
    
    if state["status"] not in ["valid", "invalid"]:
        state["status"] = "error"
        return state

    try:
        llm = ChatGoogleGenerativeAI(api_key=GEMINI_API_KEY, model="gemini-2.5-flash", temperature=0.7)

        # Build and send prompt
        prompt_text = build_prompt(state)
        messages = [
            SystemMessage(content="You are a professional travel itinerary planner."),
            HumanMessage(content=prompt_text),
        ]

        response_text = call_llm(messages, llm)

        # Parse response
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1

        if json_start == -1 or json_end == 0:
            raise ValueError("LLM response does not contain valid JSON")

        json_str = response_text[json_start:json_end]
        parsed = json.loads(json_str)

        # Build ItineraryResponse
        constraints = state["constraints"]
        days = []

        for day_data in parsed.get("days", []):
            day_number = day_data.get("day_number", 0)
            cluster = next((c for c in state["day_clusters"] if c.day_number == day_number), None)

            day_plan = DayPlan(
                day_number=day_number,
                theme=day_data.get("theme", ""),
                narrative=day_data.get("narrative", ""),
                estimated_walking_km=float(day_data.get("estimated_walking_km", 0)),
                pois=cluster.pois if cluster else [],
            )
            days.append(day_plan)

        # Ensure we have exactly n_days day plans
        while len(days) < constraints.n_days:
            days.append(
                DayPlan(
                    day_number=len(days) + 1,
                    theme="Exploration",
                    narrative="Free day for personal exploration.",
                    estimated_walking_km=0,
                    pois=[],
                )
            )

        itinerary = ItineraryResponse(
            destination=constraints.destination,
            n_days=constraints.n_days,
            days=days[: constraints.n_days],
            lodging=state["lodging"],
            transit=state["transit"],
            total_estimated_cost=float(parsed.get("total_estimated_cost", 0)) if parsed.get("total_estimated_cost") else None,
            tips=parsed.get("tips", []),
            warnings=state["validation_errors"] if state["retry_count"] >= MAX_RETRIES else [],
            generated_at=datetime.utcnow(),
        )

        state["itinerary"] = itinerary
        state["status"] = "done"

    except LLMError as e:
        state["status"] = "error"
        state["validation_errors"].append(f"Itinerary compilation failed (LLM error): {str(e)}")
    except Exception as e:
        state["status"] = "error"
        state["validation_errors"].append(f"Itinerary compilation failed: {str(e)}")

    return state
