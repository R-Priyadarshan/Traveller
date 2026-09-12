"""LangGraph state schema for the workflow."""

from typing import Literal, Optional, TypedDict

from .travel import (
    DayCluster,
    ItineraryResponse,
    LodgingOption,
    POI,
    TravelConstraints,
    TransitOption,
)


class PlannerState(TypedDict):
    """Mutable workflow state managed by LangGraph."""

    query: str
    preferences: list[str]
    constraints: Optional[TravelConstraints]
    pois: list[POI]
    day_clusters: list[DayCluster]
    lodging: list[LodgingOption]
    transit: list[TransitOption]
    validation_errors: list[str]
    status: Literal[
        "init", "researching", "logistics", "validating", "compiling", "done", "error"
    ]
    itinerary: Optional[ItineraryResponse]
    retry_count: int


def initial_state(query: str, preferences: list[str] = None) -> PlannerState:
    """Factory function to create a zeroed initial PlannerState."""
    return {
        "query": query,
        "preferences": preferences or [],
        "constraints": None,
        "pois": [],
        "day_clusters": [],
        "lodging": [],
        "transit": [],
        "validation_errors": [],
        "status": "init",
        "itinerary": None,
        "retry_count": 0,
    }
