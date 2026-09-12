"""Pydantic models for travel entities."""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator


class BudgetLevel(str, Enum):
    """Budget tier for travel planning."""

    LOW = "low"  # price_tier 1
    MEDIUM = "medium"  # price_tier 1–2
    HIGH = "high"  # price_tier 1–3
    LUXURY = "luxury"  # price_tier 1–4


class TravelRequest(BaseModel):
    """Client HTTP request payload for travel planning."""

    query: str
    preferences: list[str] = []
    budget: BudgetLevel = BudgetLevel.MEDIUM
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate query: non-empty after strip, max 500 chars."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("query must be non-empty")
        if len(stripped) > 500:
            raise ValueError("query must not exceed 500 characters")
        return stripped

    @field_validator("preferences")
    @classmethod
    def validate_preferences(cls, v: list[str]) -> list[str]:
        """Validate preferences: max 10 items."""
        if len(v) > 10:
            raise ValueError("preferences must contain at most 10 items")
        return v

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v: Optional[date]) -> Optional[date]:
        """Validate start_date: must be today or in the future (UTC)."""
        if v is not None and v < date.today():
            raise ValueError("start_date must be today or in the future")
        return v

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: Optional[date], info) -> Optional[date]:
        """Validate end_date: must be after start_date if both provided."""
        if v is not None and "start_date" in info.data:
            start_date = info.data["start_date"]
            if start_date is not None and v <= start_date:
                raise ValueError("end_date must be after start_date")
        return v


class TravelConstraints(BaseModel):
    """Structured constraints extracted by Coordinator."""

    destination: str
    n_days: int
    budget: BudgetLevel
    traveller_count: int = 1
    interests: list[str] = []
    start_date: Optional[date] = None


class POI(BaseModel):
    """Point of Interest."""

    name: str
    category: str
    description: str
    lat: float
    lon: float
    rating: Optional[float] = None
    estimated_duration_hours: float = 1.0
    price_tier: int = 1
    opening_hours: Optional[str] = None


class DayCluster(BaseModel):
    """A group of POIs assigned to a single day."""

    day_number: int
    pois: list[POI]
    centroid_lat: float
    centroid_lon: float
    total_duration_hours: float


class LodgingOption(BaseModel):
    """Accommodation option."""

    name: str
    type: str
    price_per_night: Optional[float] = None
    price_tier: int
    lat: float
    lon: float
    check_in: Optional[date] = None
    check_out: Optional[date] = None


class TransitOption(BaseModel):
    """Transport leg option."""

    mode: str
    origin: str
    destination: str
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    price_estimate: Optional[float] = None


class DayPlan(BaseModel):
    """A single day's plan within an itinerary."""

    day_number: int
    date: Optional[date] = None
    theme: str
    pois: list[POI]
    narrative: str
    estimated_walking_km: float


class ItineraryResponse(BaseModel):
    """Final itinerary response returned to client."""

    destination: str
    n_days: int
    days: list[DayPlan]
    lodging: list[LodgingOption]
    transit: list[TransitOption]
    total_estimated_cost: Optional[float] = None
    tips: list[str] = []
    warnings: list[str] = []
    generated_at: datetime
