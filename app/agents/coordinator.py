"""Coordinator agent: parses free-text travel request into structured constraints."""

import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import GEMINI_API_KEY
from app.exceptions import ConstraintExtractionError
from app.schemas import PlannerState, TravelConstraints
from .llm_utils import call_llm


def extract_constraints(query: str, llm: ChatGoogleGenerativeAI) -> TravelConstraints:
    """
    Extract structured travel constraints from free-text query using LLM.

    Args:
        query: Non-empty user query string
        llm: Configured ChatGoogleGenerativeAI instance

    Returns:
        Structured TravelConstraints object

    Raises:
        ConstraintExtractionError: If LLM output is malformed or missing required fields
    """
    system_prompt = """You are a travel planning assistant. Your task is to extract structured travel constraints from a user's free-text query.

Extract the following information:
- destination: The target destination (city or region) - REQUIRED
- n_days: Number of days for the trip (integer, 1-30) - DEFAULT to 3 if not mentioned
- budget: Budget level ("low", "medium", "high", or "luxury") - DEFAULT to "medium"
- traveller_count: Number of travellers (integer) - DEFAULT to 1 if not mentioned
- interests: List of interests or activity preferences - DEFAULT to empty list if not mentioned

IMPORTANT RULES:
1. ALWAYS return ONLY a valid JSON object with no additional text
2. If n_days is not mentioned in the query, use 3 as the default
3. If budget is not mentioned, use "medium" as default
4. Use lowercase budget values: "low", "medium", "high", "luxury"
5. Always include all 5 fields in the response

Example response:
{
  "destination": "Paris",
  "n_days": 5,
  "budget": "medium",
  "traveller_count": 2,
  "interests": ["museums", "food", "art"]
}

Example with defaults (for "I want to go to India"):
{
  "destination": "India",
  "n_days": 3,
  "budget": "medium",
  "traveller_count": 1,
  "interests": []
}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=query),
    ]

    try:
        response_text = call_llm(messages, llm)

        # Try to extract JSON from response
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            raise ConstraintExtractionError(
                "LLM response does not contain valid JSON",
                missing_fields=["entire_response"],
            )

        json_str = response_text[json_start:json_end]
        raw_constraints = json.loads(json_str)

        # Validate destination
        destination = raw_constraints.get("destination")
        if not destination or not str(destination).strip():
            raise ConstraintExtractionError(
                "destination cannot be empty",
                missing_fields=["destination"],
            )

        # Validate and default n_days
        n_days = raw_constraints.get("n_days")
        if n_days is None:
            # Default to 3 if not provided by LLM
            n_days = 3
        
        # Ensure n_days is an integer and in valid range
        try:
            n_days = int(n_days)
        except (ValueError, TypeError):
            n_days = 3  # Fallback to default if conversion fails
        
        if n_days < 1 or n_days > 30:
            n_days = 3  # Default if out of range

        # Convert to TravelConstraints with defaults
        budget_str = str(raw_constraints.get("budget", "medium")).lower()
        valid_budgets = ["low", "medium", "high", "luxury"]
        if budget_str not in valid_budgets:
            budget_str = "medium"  # Default if LLM returns invalid value
        
        traveller_count = raw_constraints.get("traveller_count", 1)
        try:
            traveller_count = int(traveller_count)
            if traveller_count < 1:
                traveller_count = 1
        except (ValueError, TypeError):
            traveller_count = 1
        
        interests = raw_constraints.get("interests", [])
        if not isinstance(interests, list):
            interests = []
        
        return TravelConstraints(
            destination=str(destination).strip(),
            n_days=n_days,
            budget=budget_str,
            traveller_count=traveller_count,
            interests=interests,
        )

    except json.JSONDecodeError as e:
        raise ConstraintExtractionError(
            f"Failed to parse LLM response as JSON: {str(e)}",
            missing_fields=["entire_response"],
        )
    except ConstraintExtractionError:
        raise
    except Exception as e:
        raise ConstraintExtractionError(
            f"Unexpected error during constraint extraction: {str(e)}",
            missing_fields=["entire_response"],
        )


def parse_intent(state: PlannerState) -> PlannerState:
    """
    Coordinator agent node: extract constraints from user query.

    Args:
        state: Current PlannerState

    Returns:
        Updated PlannerState with constraints and status
    """
    try:
        llm = ChatGoogleGenerativeAI(api_key=GEMINI_API_KEY, model="gemini-2.5-flash", temperature=0)
        constraints = extract_constraints(state["query"], llm)

        state["constraints"] = constraints
        state["status"] = "researching"

    except ConstraintExtractionError as e:
        state["status"] = "error"
        state["validation_errors"] = [f"Constraint extraction failed: {str(e)}"]

    return state
