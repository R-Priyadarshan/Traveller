# Implementation Plan: Travel Planner

## Overview

Implement the Travel Planner multi-agent application end-to-end, following the design and requirements
documents. The build is structured in four layers: (1) scaffolding and schemas, (2) tool
implementations, (3) agent implementations, (4) workflow + API wiring, and (5) tests. Each task is
independently completable and maps to one or more requirements.

## Tasks

- [ ] 1. Project scaffold and configuration
  - Create the full directory structure: `app/`, `app/schemas/`, `app/tools/`, `app/agents/`, `app/workflow/`
  - Create all `__init__.py` files
  - Create `app/config.py` loading `OPENAI_API_KEY`, `TAVILY_API_KEY`, `MAX_RETRIES=3`, `MAX_POIS_PER_DAY=5`, `MAX_HOURS_PER_DAY=10`, `MAX_POIS_TOTAL=30` from env via `python-dotenv`; raise `RuntimeError` on startup if either API key is absent
  - Create `pyproject.toml` and `requirements.txt` with pinned dependencies: `fastapi>=0.110.0`, `uvicorn>=0.28.0`, `langgraph>=0.0.30`, `langchain-openai>=0.1.0`, `langchain-community>=0.0.28`, `pydantic>=2.6.0`, `scikit-learn>=1.4.0`, `numpy>=1.26.0`, `python-dotenv>=1.0.0`, `hypothesis`, `pytest`, `pytest-asyncio`, `httpx`
  - Create `.env` template with placeholder keys (no real values)
  - **Requirement:** 16.1

- [ ] 2. Pydantic schemas — travel entities (`app/schemas/travel.py`)
  - Implement `BudgetLevel` enum: `LOW`, `MEDIUM`, `HIGH`, `LUXURY`
  - Implement `TravelRequest` with validators: strip + non-empty + ≤500 chars for `query`; max 10 for `preferences`; `start_date` ≥ today UTC; `end_date` > `start_date`; default `budget = BudgetLevel.MEDIUM`
  - Implement `TravelConstraints`, `POI`, `DayCluster`, `LodgingOption`, `TransitOption`, `DayPlan`
  - Implement `ItineraryResponse` including `warnings: list[str] = []`
  - **Requirements:** 2.1, 2.2, 2.3, 2.4, 2.5, 12.4

- [ ] 3. Pydantic schemas — LangGraph state (`app/schemas/state.py`)
  - Implement `PlannerState` as `TypedDict` with all fields from the design
  - Export `initial_state()` factory returning a zeroed `PlannerState` with `status="init"` and `retry_count=0`
  - **Requirement:** 11.1

- [ ] 4. Geo tools — Haversine and nearest-neighbour route (`app/tools/geo.py`)
  - Implement `haversine(lat1, lon1, lat2, lon2) -> float`: validate numeric inputs within bounds, raise `ValueError` on violation; compute great-circle distance in km
  - Implement `compute_centroid(pois) -> tuple[float, float]`: arithmetic mean of lat/lon
  - Implement `nearest_neighbour_route(pois) -> list[POI]`: greedy from index 0, repeatedly select closest unvisited by Haversine
  - **Requirements:** 6.1–6.6, 8.1–8.3

- [ ] 5. Geo tools — K-Means clustering (`app/tools/geo.py`)
  - Implement `cluster_pois(pois, n_clusters) -> list[DayCluster]`: guard `n_clusters >= 1` and `len(pois) >= n_clusters` (raise `ValueError`); run `KMeans(n_clusters, random_state=42)`; per cluster apply `nearest_neighbour_route`, `compute_centroid`, sum durations; assign `day_number` 1-indexed
  - Implement `order_cluster_by_haversine` as alias for `nearest_neighbour_route`
  - **Requirements:** 7.1–7.6

- [ ] 6. Search tools — Tavily wrapper (`app/tools/search.py`)
  - Define `SearchResult` model and `SearchError` exception
  - Implement `search(query, max_results=5)`: validate args; retry with exponential back-off (3 attempts, base 1s, cap 16s, jitter); cache by exact query string per invocation; raise `SearchError` on exhaustion
  - Implement `batch_search(queries)`: concurrent execution; empty list at position of any failed query
  - **Requirements:** 9.1–9.6, 15.3

- [ ] 7. Coordinator agent (`app/agents/coordinator.py`)
  - Define `ConstraintExtractionError(ValueError)` with `missing_fields: list[str]`
  - Implement `extract_constraints(query, llm)`: static `SystemMessage` + `HumanMessage(query)` only; parse JSON; validate destination non-empty and n_days in 1–30; raise `ConstraintExtractionError` on any failure
  - Implement `parse_intent(state)`: call `extract_constraints`; set `state.constraints` and `state.status="researching"` on success; set `state.status="error"` on failure
  - **Requirements:** 3.1–3.5, 16.2

- [ ] 8. Researcher agent (`app/agents/researcher.py`)
  - Implement `search_pois(constraints, search_tool)`: build ≥1 Tavily query from destination + interests
  - Implement `rank_pois(raw, constraints, llm)`: deduplicate by name; LLM ranking; filter invalid coords; cap at `MAX_POIS_TOTAL`
  - Implement `curate_pois(state)`: on zero valid POIs set `state.status="error"` with message; otherwise populate `state.pois`
  - **Requirements:** 4.1–4.5, 15.4

- [ ] 9. Logistics agent (`app/agents/logistics.py`)
  - Implement `find_lodging(constraints, llm) -> list[LodgingOption]` (≥1 result)
  - Implement `find_transit(constraints, search_tool) -> list[TransitOption]` (empty list allowed for local trips)
  - Implement `assign_days(pois, n_days)`: guard `len(pois) >= n_days`; call `cluster_pois`
  - Implement `plan_logistics(state)`: check preconditions; run all three sub-functions; set `state.status="logistics"` on success or `"error"` if POI count is insufficient; reduce `n_clusters` if invalid POIs were filtered
  - **Requirements:** 5.1–5.6, 15.5

- [ ] 10. Validator agent (`app/agents/validator.py`)
  - Implement `check_day_capacity(clusters) -> list[str]`
  - Implement `check_duration(clusters) -> list[str]`
  - Implement `check_budget(pois, lodging, budget) -> list[str]`: tier rules 1–4 per `BudgetLevel`; error on out-of-range tiers
  - Implement `validate(state)`: aggregate all errors; set `state.status` and increment `state.retry_count`
  - **Requirements:** 10.1–10.6, 14.1–14.6

- [ ] 11. Compiler agent (`app/agents/compiler.py`)
  - Implement `build_prompt(state) -> str`
  - Implement `parse_llm_output(raw) -> ItineraryResponse`: strict Pydantic parse
  - Implement `compile_itinerary(state)`: call LLM; validate `len(days) == n_days`; set `generated_at`; populate `warnings` from `validation_errors` when `retry_count >= MAX_RETRIES`; set `state.status="done"`
  - **Requirements:** 12.2, 12.3, 13.1–13.5

- [ ] 12. OpenAI retry wrapper (`app/exceptions.py` + helper)
  - Define `LLMError(RuntimeError)`
  - Implement `call_llm(messages, llm) -> str`: exponential back-off (3 retries, base 1s, cap 16s, jitter) on `RateLimitError` and timeouts; raise `LLMError` on exhaustion
  - Use `call_llm` in all agents that call OpenAI
  - **Requirements:** 15.1, 15.2

- [ ] 13. LangGraph workflow (`app/workflow/graph.py`)
  - Implement `should_replan(state) -> str`
  - Implement `build_graph() -> CompiledGraph`: wire five nodes with fixed edges and conditional edge from validator; compile with `MemorySaver`
  - **Requirements:** 11.1–11.5, 12.1

- [ ] 14. FastAPI entry point (`app/main.py`)
  - Implement `GET /health` → `{"status": "ok"}`
  - Implement `POST /plan`: validate request; build initial state; invoke graph; return 200 (valid) or 206 (exhausted); 30-second timeout
  - Register exception handlers: `ConstraintExtractionError` → 422; `SearchError` / `LLMError` → 503
  - **Requirements:** 1.1–1.5, 12.2, 15.1, 15.2

- [ ] 15. Unit tests — geo tools (`tests/test_geo.py`)
  - `haversine`: identical points → 0.0; London↔Paris ±0.001 km; NYC↔LA ±0.001 km; symmetry; `ValueError` on bad inputs
  - `nearest_neighbour_route`: output is permutation of input for multiple fixed lists
  - `cluster_pois`: partition property; correct cluster count; `ValueError` on under-count or `n_clusters < 1`; centroid and duration sum correctness
  - **Requirements:** 6.1–6.6, 7.1–7.6, 8.1–8.3

- [ ] 16. Unit tests — search tools (`tests/test_search.py`)
  - Mock Tavily: result cap; retry-then-succeed (3 total calls); exhaustion → `SearchError`; cache (1 real call for 2 identical queries); `batch_search` order and partial failure
  - **Requirements:** 9.1–9.6

- [ ] 17. Unit tests — agents (`tests/test_agents.py`)
  - Coordinator: valid JSON → constraints set; malformed JSON → `ConstraintExtractionError`; `n_days=0` → error
  - Researcher: valid results → `len(pois) <= 30` and coords valid; zero results → `status="error"`
  - Logistics: 3 POIs + `n_days=3` → 3 clusters; 2 POIs + `n_days=3` → `status="error"`
  - Validator: each rule individually violated → correct error string; clean state → `status="valid"`
  - Compiler: valid state → `ItineraryResponse` with correct day count; exhausted state → `warnings` populated
  - **Requirements:** 3.1–3.5, 4.1–4.5, 5.1–5.6, 10.1–10.6, 13.1–13.5

- [ ] 18. Unit tests — workflow (`tests/test_workflow.py`)
  - `build_graph()` compiles without error
  - `should_replan` routing: invalid + low count → `"replan"`; valid → `"compile"`; exhausted → `"compile"`
  - Happy path (all mocked): final `status="done"`, `retry_count=0`
  - Retry path: Validator fails twice then passes; `retry_count=2`
  - Loop exhaustion: Validator always invalid; `retry_count=3`; Compiler still invoked
  - **Requirements:** 11.1–11.5, 12.1

- [ ] 19. Property-based tests (`tests/test_properties.py`)
  - Haversine symmetry, non-negativity, identity
  - Nearest-neighbour permutation property
  - Cluster partition and duration-sum properties
  - Validation soundness (`status=="valid"` iff `errors==[]`)
  - Budget monotonicity
  - **Requirements:** Design properties 1–9

- [ ] 20. Integration test (`tests/test_integration.py`)
  - `pytest.mark.integration`; skip unless API keys present
  - POST `{"query": "3 days in Paris for 2", "budget": "medium"}` → HTTP 200, valid `ItineraryResponse`, `len(days)==3`
  - GET `/health` → `{"status": "ok"}`
  - **Requirements:** 1.1, 1.2, 13.4

## Task Dependency Graph

```json
{
  "waves": [
    {
      "wave": 1,
      "tasks": [1]
    },
    {
      "wave": 2,
      "tasks": [2]
    },
    {
      "wave": 3,
      "tasks": [3, 12]
    },
    {
      "wave": 4,
      "tasks": [4, 6, 7]
    },
    {
      "wave": 5,
      "tasks": [5, 8, 10, 11]
    },
    {
      "wave": 6,
      "tasks": [9]
    },
    {
      "wave": 7,
      "tasks": [13]
    },
    {
      "wave": 8,
      "tasks": [14]
    },
    {
      "wave": 9,
      "tasks": [15, 16, 17, 18, 19]
    },
    {
      "wave": 10,
      "tasks": [20]
    }
  ]
}
```

## Notes

- Tasks 4 and 5 both write to `app/tools/geo.py`; complete them sequentially.
- Task 12 (LLM retry wrapper) should be completed before tasks 7, 8, 9, and 11 are finalised so all agents use the shared retry helper.
- Integration tests (task 20) require live API keys and should be excluded from the default CI run via `pytest -m "not integration"`.
- The `MemorySaver` checkpointer used in task 13 is suitable for development; swap to a Redis or PostgreSQL checkpointer before deploying to production.
- All LLM-generated JSON must be parsed through strict Pydantic models — never passed raw to downstream consumers.
