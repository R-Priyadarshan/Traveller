"""Validator agent: enforces business rules before compilation."""

from app.config import MAX_POIS_PER_DAY, MAX_HOURS_PER_DAY
from app.schemas import PlannerState, BudgetLevel


def check_day_capacity(state: PlannerState) -> list[str]:
    """Check that no day cluster exceeds MAX_POIS_PER_DAY."""
    errors = []
    for cluster in state["day_clusters"]:
        if len(cluster.pois) > MAX_POIS_PER_DAY:
            errors.append(f"Day {cluster.day_number} has {len(cluster.pois)} POIs, max is {MAX_POIS_PER_DAY}")
    return errors


def check_duration(state: PlannerState) -> list[str]:
    """Check that no day cluster exceeds MAX_HOURS_PER_DAY."""
    errors = []
    for cluster in state["day_clusters"]:
        if cluster.total_duration_hours > MAX_HOURS_PER_DAY:
            errors.append(
                f"Day {cluster.day_number} has {cluster.total_duration_hours:.1f} hours of activities, max is {MAX_HOURS_PER_DAY}"
            )
    return errors


def check_budget(state: PlannerState) -> list[str]:
    """Check budget compatibility of POIs and lodging."""
    errors = []
    
    if state["constraints"] is None:
        return errors
    
    budget = state["constraints"].budget

    # Budget tier rules
    tier_max = {
        BudgetLevel.LOW: 1,
        BudgetLevel.MEDIUM: 2,
        BudgetLevel.HIGH: 3,
        BudgetLevel.LUXURY: 4,
    }

    max_tier = tier_max.get(budget, 2)

    # Check all POIs
    for poi in state["pois"]:
        if poi.price_tier < 1 or poi.price_tier > 4:
            errors.append(f"POI '{poi.name}' has invalid price_tier: {poi.price_tier}")
        elif poi.price_tier > max_tier:
            errors.append(
                f"POI '{poi.name}' (tier {poi.price_tier}) exceeds budget {budget} (max tier {max_tier})"
            )

    # Check all lodging
    for lodge in state["lodging"]:
        if lodge.price_tier < 1 or lodge.price_tier > 4:
            errors.append(f"Lodging '{lodge.name}' has invalid price_tier: {lodge.price_tier}")
        elif lodge.price_tier > max_tier:
            errors.append(
                f"Lodging '{lodge.name}' (tier {lodge.price_tier}) exceeds budget {budget} (max tier {max_tier})"
            )

    return errors


def validate(state: PlannerState) -> PlannerState:
    """
    Validator agent node: check all business rules.

    Args:
        state: Current PlannerState

    Returns:
        Updated PlannerState with validation results
    """
    errors = []

    # Run all checks
    errors.extend(check_day_capacity(state))
    errors.extend(check_duration(state))
    errors.extend(check_budget(state))

    # Update state
    state["validation_errors"] = errors

    if not errors:
        state["status"] = "valid"
    else:
        state["status"] = "invalid"
        state["retry_count"] = state.get("retry_count", 0) + 1

    return state
