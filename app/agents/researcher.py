"""Researcher agent: discovers and ranks POIs."""

import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import GEMINI_API_KEY, MAX_POIS_TOTAL
from app.exceptions import SearchError
from app.schemas import PlannerState, POI, TravelConstraints
from app.tools import search
from .llm_utils import call_llm


def search_pois(constraints: TravelConstraints, search_tool=None) -> list[dict]:
    """
    Search for POIs using Tavily.

    Args:
        constraints: TravelConstraints object
        search_tool: Optional search tool function (defaults to app.tools.search)

    Returns:
        List of raw search result dicts
    """
    if search_tool is None:
        search_tool = search

    destination = constraints.destination
    interests_str = ", ".join(constraints.interests) if constraints.interests else "attractions"

    query = f"best {interests_str} in {destination} tourist attractions"

    try:
        results = search_tool(query, max_results=10)
        return [{"url": r.url, "content": r.content} for r in results]
    except SearchError as e:
        return []


def rank_pois(
    raw_results: list[dict], constraints: TravelConstraints, llm: ChatOpenAI
) -> list[POI]:
    """
    Rank and structure raw search results into POI objects using LLM.

    Args:
        raw_results: Raw search result dicts
        constraints: TravelConstraints object
        llm: Configured ChatOpenAI instance

    Returns:
        List of ranked POI objects (at most MAX_POIS_TOTAL)
    """
    if not raw_results:
        return []

    # Build ranking prompt
    raw_text = "\n\n".join(
        [f"Source: {r.get('url', 'Unknown')}\nContent: {r.get('content', '')}" for r in raw_results]
    )

    system_prompt = f"""You are a travel curator. Analyze the provided search results for {constraints.destination} and extract the top POIs.

For each POI, provide:
- name: Name of the attraction
- category: Type (museum, restaurant, park, landmark, etc.)
- description: Brief 1-2 sentence description
- lat: Latitude (use plausible estimates if not provided)
- lon: Longitude (use plausible estimates if not provided)
- rating: Rating 0-5 (estimate if not found)
- estimated_duration_hours: How long to visit (float)
- price_tier: 1 (free/cheap) to 4 (expensive)
- opening_hours: Hours if available

Return a JSON array with up to {MAX_POIS_TOTAL} POIs. Use plausible coordinates for {constraints.destination}.

Example output format:
[
  {
    "name": "Eiffel Tower",
    "category": "landmark",
    "description": "Iconic iron lattice tower in Paris",
    "lat": 48.858,
    "lon": 2.294,
    "rating": 4.8,
    "estimated_duration_hours": 2.0,
    "price_tier": 2,
    "opening_hours": "9am-12:45am"
  }
]"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=raw_text),
    ]

    try:
        response_text = call_llm(messages, llm)

        # Extract JSON array
        json_start = response_text.find("[")
        json_end = response_text.rfind("]") + 1

        if json_start == -1 or json_end == 0:
            return []

        json_str = response_text[json_start:json_end]
        raw_pois = json.loads(json_str)

        # Parse into POI objects with coordinate validation
        ranked_pois = []
        for item in raw_pois:
            try:
                # Validate lat/lon are within valid ranges
                lat = float(item.get("lat", 0))
                lon = float(item.get("lon", 0))

                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    continue  # Skip invalid coordinates

                poi = POI(
                    name=item.get("name", "Unknown"),
                    category=item.get("category", "unknown"),
                    description=item.get("description", ""),
                    lat=lat,
                    lon=lon,
                    rating=float(item.get("rating", 0)) if item.get("rating") else None,
                    estimated_duration_hours=float(item.get("estimated_duration_hours", 1.0)),
                    price_tier=int(item.get("price_tier", 1)),
                    opening_hours=item.get("opening_hours"),
                )
                ranked_pois.append(poi)
            except (ValueError, TypeError):
                continue  # Skip malformed entries

        return ranked_pois[:MAX_POIS_TOTAL]

    except json.JSONDecodeError:
        return []
    except Exception:
        return []


def curate_pois(state: PlannerState) -> PlannerState:
    """
    Researcher agent node: discover and rank POIs.

    Args:
        state: Current PlannerState

    Returns:
        Updated PlannerState with POIs
    """
    if state["constraints"] is None:
        state["validation_errors"].append("No constraints available for POI search")
        state["status"] = "error"
        return state

    try:
        llm = ChatGoogleGenerativeAI(api_key=GEMINI_API_KEY, model="gemini-2.5-flash", temperature=0.3)

        # Search for raw POIs
        raw_results = search_pois(state["constraints"])

        if not raw_results:
            state["status"] = "error"
            state["validation_errors"].append("No POIs found for destination")
            return state

        # Rank and structure
        pois = rank_pois(raw_results, state["constraints"], llm)

        if not pois:
            state["status"] = "error"
            state["validation_errors"].append("No POIs found for destination")
            return state

        state["pois"] = pois

    except Exception as e:
        state["status"] = "error"
        state["validation_errors"].append(f"POI curation failed: {str(e)}")

    return state
