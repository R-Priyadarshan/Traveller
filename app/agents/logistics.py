"""Logistics agent: plans lodging, transit, and daily routes."""

import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import GEMINI_API_KEY
from app.schemas import PlannerState, LodgingOption, TransitOption
from app.tools import cluster_pois
from .llm_utils import call_llm


def find_lodging(constraints, llm: ChatGoogleGenerativeAI) -> list[LodgingOption]:
    """
    Find lodging options using LLM.

    Args:
        constraints: TravelConstraints object
        llm: Configured ChatOpenAI instance

    Returns:
        List of LodgingOption objects (at least 1)
    """
    system_prompt = f"""You are a travel accommodation assistant. Suggest lodging options for {constraints.destination}.

Consider the budget level: {constraints.budget}
Number of travellers: {constraints.traveller_count}
Trip duration: {constraints.n_days} days

Return a JSON array with 2-3 realistic lodging options. Each should have:
- name: Hotel/accommodation name
- type: hotel, hostel, airbnb, resort, etc.
- price_per_night: Estimated price in USD
- price_tier: 1 (budget) to 4 (luxury)
- lat: Latitude
- lon: Longitude
- check_in: "YYYY-MM-DD" (optional)
- check_out: "YYYY-MM-DD" (optional)

Example:
[
  {
    "name": "Hotel Le Marais",
    "type": "hotel",
    "price_per_night": 150,
    "price_tier": 2,
    "lat": 48.86,
    "lon": 2.36
  }
]"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Find lodging in {constraints.destination}"),
    ]

    try:
        response_text = call_llm(messages, llm)
        json_start = response_text.find("[")
        json_end = response_text.rfind("]") + 1

        if json_start == -1 or json_end == 0:
            return []

        json_str = response_text[json_start:json_end]
        raw_lodging = json.loads(json_str)

        options = []
        for item in raw_lodging:
            try:
                option = LodgingOption(
                    name=item.get("name", "Lodging"),
                    type=item.get("type", "hotel"),
                    price_per_night=float(item.get("price_per_night")) if item.get("price_per_night") else None,
                    price_tier=int(item.get("price_tier", 2)),
                    lat=float(item.get("lat", 0)),
                    lon=float(item.get("lon", 0)),
                )
                options.append(option)
            except (ValueError, TypeError):
                continue

        return options[:3] if options else []

    except Exception:
        return []


def find_transit(constraints, search_tool=None) -> list[TransitOption]:
    """
    Find transit options.

    Args:
        constraints: TravelConstraints object
        search_tool: Optional search tool

    Returns:
        List of TransitOption objects (may be empty for local trips)
    """
    # For now, return empty list (in production, would search for flights, trains, etc.)
    # This represents a local trip where transit is within the city
    return []


def assign_days(pois: list, n_days: int):
    """
    Assign POIs to days and cluster geographically.

    Args:
        pois: List of POI objects
        n_days: Number of days

    Returns:
        List of DayCluster objects
    """
    if not pois or n_days < 1:
        return []

    if len(pois) < n_days:
        # Not enough POIs for clustering
        return []

    try:
        return cluster_pois(pois, n_days)
    except ValueError:
        return []


def plan_logistics(state: PlannerState) -> PlannerState:
    """
    Logistics agent node: plan lodging, transit, and daily routes.

    Args:
        state: Current PlannerState

    Returns:
        Updated PlannerState with logistics information
    """
    if state["constraints"] is None or state["status"] != "researching":
        state["status"] = "error"
        state["validation_errors"].append("Invalid state for logistics planning")
        return state

    try:
        llm = ChatGoogleGenerativeAI(api_key=GEMINI_API_KEY, model="gemini-2.5-flash", temperature=0.5)

        # Check POI count
        if len(state["pois"]) < state["constraints"].n_days:
            state["status"] = "error"
            state["validation_errors"].append(
                f"Not enough POIs ({len(state['pois'])}) for {state['constraints'].n_days} days"
            )
            return state

        # Cluster POIs into days
        day_clusters = assign_days(state["pois"], state["constraints"].n_days)

        if not day_clusters:
            state["status"] = "error"
            state["validation_errors"].append("Failed to create day clusters")
            return state

        state["day_clusters"] = day_clusters

        # Find lodging
        lodging = find_lodging(state["constraints"], llm)
        if not lodging:
            state["status"] = "error"
            state["validation_errors"].append("Failed to find lodging options")
            return state

        state["lodging"] = lodging

        # Find transit
        transit = find_transit(state["constraints"])
        state["transit"] = transit

        state["status"] = "logistics"

    except Exception as e:
        state["status"] = "error"
        state["validation_errors"].append(f"Logistics planning failed: {str(e)}")

    return state
