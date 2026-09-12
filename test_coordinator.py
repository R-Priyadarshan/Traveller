"""Test just the coordinator."""
from app.agents.coordinator import extract_constraints, parse_intent
from app.schemas import initial_state
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import GEMINI_API_KEY

# Test extract_constraints directly
llm = ChatGoogleGenerativeAI(api_key=GEMINI_API_KEY, model="gemini-2.5-flash", temperature=0)

query = "3 days in Paris with friends, we like museums and food"

print(f"Testing extract_constraints with query: {query}\n")

try:
    constraints = extract_constraints(query, llm)
    print(f"Success! Constraints: {constraints}")
    print(f"Budget: {constraints.budget}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")

# Test parse_intent
print("\n\nTesting parse_intent...")
state = initial_state(query, preferences=["art", "food"])
print(f"Initial state constraints: {state['constraints']}")

try:
    updated_state = parse_intent(state)
    print(f"Updated state status: {updated_state['status']}")
    print(f"Updated state constraints: {updated_state['constraints']}")
    if updated_state['validation_errors']:
        print(f"Validation errors: {updated_state['validation_errors']}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
