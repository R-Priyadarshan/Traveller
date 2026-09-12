# Requirements Document

## Introduction

The Travel Planner is a multi-agent AI system that accepts a natural-language travel request and
produces a structured, day-by-day itinerary. The system orchestrates five specialised agents
(Coordinator, Researcher, Logistics, Validator, Compiler) through a LangGraph state machine,
using OpenAI for language tasks and Tavily for real-time search. Geographic route optimisation
is performed locally via K-Means clustering and Haversine distance calculations.

This document captures the functional and non-functional requirements derived from the approved
design document.

---

## Glossary

- **System**: The Travel Planner application as a whole.
- **API**: The FastAPI HTTP entry point exposed to clients.
- **Coordinator**: The first agent node; parses free-text into structured constraints.
- **Researcher**: The second agent node; discovers and ranks Points of Interest.
- **Logistics_Agent**: The third agent node; plans lodging, transit, and geo-clustered daily routes.
- **Validator**: The fourth agent node; deterministic business-rule gate.
- **Compiler**: The fifth agent node; synthesises the final human-readable itinerary.
- **Workflow**: The LangGraph-compiled state machine that sequences agent execution.
- **Geo_Tools**: The local module providing Haversine distance and K-Means clustering.
- **Search_Tools**: The Tavily wrapper module providing retry, caching, and result normalisation.
- **TravelRequest**: The Pydantic model representing a client's HTTP request payload.
- **TravelConstraints**: The structured output of the Coordinator, capturing destination, duration, budget, traveller count, and interests.
- **POI**: A Point of Interest — a named location with geographic coordinates, category, and metadata.
- **DayCluster**: A group of POIs assigned to a single day, ordered by nearest-neighbour routing.
- **LodgingOption**: A candidate accommodation with price tier and geographic coordinates.
- **TransitOption**: A candidate transport leg (flight, train, bus, or car).
- **PlannerState**: The LangGraph typed-dict representing all mutable workflow state.
- **ItineraryResponse**: The final Pydantic response model returned to the client.
- **DayPlan**: A single day's plan within an ItineraryResponse, including narrative and POI list.
- **BudgetLevel**: An enum with values LOW, MEDIUM, HIGH, and LUXURY.
- **MAX_RETRIES**: A configuration constant bounding the number of re-plan cycles.
- **MAX_POIS_PER_DAY**: A configuration constant (default 5) bounding POIs per day cluster.
- **MAX_HOURS_PER_DAY**: A configuration constant bounding total activity hours per day.
- **MAX_POIS_TOTAL**: A configuration constant (default 30) bounding total POIs returned by the Researcher.

---

## Requirements

### Requirement 1: HTTP API Entry Point

**User Story:** As a client application, I want a documented HTTP API, so that I can submit travel
requests and receive structured itinerary responses.

#### Acceptance Criteria

1. WHEN a client sends a valid `POST /plan` request, THE API SHALL invoke the Workflow and return
   an `ItineraryResponse` with HTTP status 200 within 30 seconds.
2. WHEN a client sends a `GET /health` request, THE API SHALL return HTTP status 200 with a JSON
   body containing at minimum `{"status": "ok"}`.
3. IF the `TravelRequest` payload fails Pydantic validation, THEN THE API SHALL return HTTP
   status 422 with a structured error body listing each invalid field by name and reason.
4. IF the Workflow raises an error due to exhausted OpenAI or Tavily retries, THEN THE API SHALL
   return HTTP status 503 with a structured error body identifying the failing dependency.
5. THE API SHALL not invoke the Workflow until all `TravelRequest` fields have passed Pydantic
   validation.

---

### Requirement 2: Travel Request Validation

**User Story:** As a client, I want the system to validate my travel request, so that I receive
clear feedback when my input is malformed or out of range.

#### Acceptance Criteria

1. IF `query` is empty, consists solely of whitespace, or exceeds 500 Unicode characters, THEN
   THE API SHALL reject the request with HTTP 422 and a structured error body identifying the
   `query` field.
2. IF `preferences` contains more than 10 items, THEN THE API SHALL reject the request with HTTP
   422 and a structured error body identifying the `preferences` field.
3. IF `start_date` is provided and is before the current UTC date at the time of the request,
   THEN THE API SHALL reject the request with HTTP 422.
4. IF both `start_date` and `end_date` are provided and `end_date` is not strictly after
   `start_date`, THEN THE API SHALL reject the request with HTTP 422.
5. WHERE `budget` is omitted from the request, THE API SHALL default to `BudgetLevel.MEDIUM`.

---

### Requirement 3: Coordinator Agent — Constraint Extraction

**User Story:** As a traveller, I want the system to understand my free-text travel request, so
that it can produce a plan aligned with my intent.

#### Acceptance Criteria

1. WHEN the Coordinator receives a non-empty query, THE Coordinator SHALL invoke the OpenAI LLM
   to extract a `TravelConstraints` object containing at minimum `destination` and `n_days`.
2. WHEN the LLM returns valid JSON for the constraints, THE Coordinator SHALL populate
   `state.constraints` and set `state.status` to `"researching"`.
3. IF the LLM returns malformed JSON, omits required fields, or returns an empty string for
   `destination`, THEN THE Coordinator SHALL raise a `ConstraintExtractionError` with a message
   listing each missing or unparseable field, causing THE API to return HTTP 422.
4. THE Coordinator SHALL pass the user query exclusively as a `HumanMessage`; the extraction
   system prompt SHALL be static and never interpolated with user-supplied content.
5. THE `TravelConstraints.n_days` extracted by THE Coordinator SHALL be clamped to the range
   1 to 30 inclusive; if the LLM returns a value outside this range, THE Coordinator SHALL
   raise a `ConstraintExtractionError`.

---

### Requirement 4: Researcher Agent — POI Discovery and Ranking

**User Story:** As a traveller, I want the system to find and rank relevant attractions for my
destination, so that my itinerary includes the most suitable activities.

#### Acceptance Criteria

1. WHEN the Researcher receives a populated `state.constraints`, THE Researcher SHALL execute at
   least one Tavily search query for POIs at the target destination.
2. WHEN raw search results are returned, THE Researcher SHALL call the OpenAI LLM to deduplicate
   and rank them into a list of `POI` objects.
3. THE Researcher SHALL return at most `MAX_POIS_TOTAL` (default 30) `POI` objects in
   `state.pois`.
4. THE Researcher SHALL ensure every `POI` in `state.pois` has valid `lat` and `lon` coordinates
   within the ranges −90 to 90 and −180 to 180 respectively.
5. IF Tavily returns zero results or all results fail coordinate extraction, THEN THE Researcher
   SHALL set `state.status` to `"error"` and add `"No POIs found for destination"` to
   `state.validation_errors`.

---

### Requirement 5: Logistics Agent — Lodging, Transit, and Route Planning

**User Story:** As a traveller, I want the system to plan my accommodation, transport, and
daily tour routes, so that I have a practical, geographically optimised itinerary.

#### Acceptance Criteria

1. WHEN the Logistics_Agent is invoked with `state.status == "researching"`, a non-empty
   `state.pois`, and `state.constraints.n_days` ≥ 1, THE Logistics_Agent SHALL produce exactly
   `n_days` `DayCluster` objects in `state.day_clusters`.
2. WHEN clustering POIs, THE Logistics_Agent SHALL call `Geo_Tools.cluster_pois` with the full
   POI list and `n_days` as the cluster count.
3. WHEN the Logistics_Agent searches for accommodation, THE Logistics_Agent SHALL populate
   `state.lodging` with at least one `LodgingOption`.
4. WHEN the Logistics_Agent searches for transit, THE Logistics_Agent SHALL populate
   `state.transit`; this list MAY be empty when origin and destination are the same city.
5. WHEN the Logistics_Agent completes successfully, THE Logistics_Agent SHALL set `state.status`
   to `"logistics"`.
6. IF `len(state.pois) < state.constraints.n_days`, THEN THE Logistics_Agent SHALL set
   `state.status` to `"error"` and add a descriptive message to `state.validation_errors`
   rather than calling `cluster_pois`.

---

### Requirement 6: Geo Tools — Haversine Distance

**User Story:** As a system component, I want an accurate geographic distance function, so that
route ordering and cluster centroid calculations are correct.

#### Acceptance Criteria

1. THE Geo_Tools SHALL implement a `haversine` function accepting two lat/lon pairs in degrees
   and returning the great-circle distance in kilometres as a non-negative float.
2. WHEN both coordinate pairs are identical, THE `haversine` function SHALL return exactly 0.0.
3. THE `haversine` function SHALL be symmetric: `haversine(lat1, lon1, lat2, lon2)` and
   `haversine(lat2, lon2, lat1, lon1)` SHALL differ by no more than 1×10⁻⁹ km.
4. IF any input latitude is outside −90 to 90, or any input longitude is outside −180 to 180,
   or any input is non-numeric, THEN THE `haversine` function SHALL raise a `ValueError`.
5. FOR known reference pairs (e.g., London to Paris ≈ 341 km, New York to Los Angeles ≈ 3,940 km),
   THE `haversine` function SHALL return a value within ±0.001 km of the accepted great-circle
   distance.
6. THE `haversine` function SHALL return a value no greater than 20,037 km (half Earth's
   circumference) for any valid input pair.

---

### Requirement 7: Geo Tools — POI Clustering

**User Story:** As a system component, I want POIs grouped into geographically coherent daily
clusters, so that each day's activities are physically near each other.

#### Acceptance Criteria

1. WHEN `cluster_pois` is called with a list of POIs and `n_clusters`, THE Geo_Tools SHALL
   return exactly `n_clusters` `DayCluster` objects with `day_number` assigned 1-indexed
   sequentially (1, 2, …, n_clusters).
2. THE Geo_Tools SHALL ensure that every input POI appears in exactly one output `DayCluster`
   (partition property: union equals full input set, clusters are pairwise disjoint).
3. WHEN ordering POIs within a cluster, THE Geo_Tools SHALL apply the nearest-neighbour
   Haversine route: start from the first POI in the cluster, then at each step append the
   unvisited POI with the smallest Haversine distance from the current position.
4. IF `len(pois) < n_clusters` or `n_clusters < 1`, THEN THE Geo_Tools SHALL raise a
   `ValueError` rather than producing empty clusters.
5. THE Geo_Tools SHALL set `DayCluster.total_duration_hours` to the arithmetic sum of
   `estimated_duration_hours` across all POIs in that cluster.
6. THE Geo_Tools SHALL set `DayCluster.centroid_lat` and `DayCluster.centroid_lon` to the
   arithmetic mean of the `lat` and `lon` values of all POIs in that cluster respectively.

---

### Requirement 8: Geo Tools — Nearest-Neighbour Route

**User Story:** As a system component, I want a nearest-neighbour tour ordering, so that the
walking route within each day cluster is locally optimised.

#### Acceptance Criteria

1. WHEN `nearest_neighbour_route` is called with a non-empty POI list, THE Geo_Tools SHALL
   return a list that is a permutation of the input — every input POI appears exactly once.
2. THE Geo_Tools SHALL start the route from the first POI in the input list.
3. WHEN building the route, THE Geo_Tools SHALL at each step select the unvisited POI whose
   Haversine distance from the current position is minimal.

---

### Requirement 9: Search Tools — Tavily Wrapper

**User Story:** As a system component, I want a resilient Tavily search wrapper, so that
transient API failures do not immediately propagate to the workflow.

#### Acceptance Criteria

1. WHEN `search` is called with a non-empty query and `1 ≤ max_results ≤ 20`, THE Search_Tools
   SHALL return a list of `SearchResult` objects of length at most `max_results`.
2. WHEN a Tavily API call fails with a network error, timeout, or HTTP 4xx/5xx response, THE
   Search_Tools SHALL retry using exponential back-off with jitter for at most 3 attempts
   (base delay 1 s, cap at 16 s) before raising a `SearchError`.
3. IF all 3 retry attempts are exhausted, THEN THE Search_Tools SHALL raise `SearchError`,
   which THE API SHALL translate to HTTP 503.
4. THE Search_Tools SHALL cache results by exact query string, scoped to the current workflow
   invocation, to avoid redundant API calls for identical queries.
5. WHEN `batch_search` is called with multiple queries, THE Search_Tools SHALL issue all
   queries concurrently and return results in the same order as the input query list.
6. IF any individual query in a `batch_search` call raises `SearchError` after retries, THE
   Search_Tools SHALL still return results for the remaining queries and include an empty list
   for the failed query's position.

---

### Requirement 10: Validator Agent — Business-Rule Enforcement

**User Story:** As a travel planner, I want the system to enforce practical constraints on the
itinerary, so that plans are realistic and budget-appropriate.

#### Acceptance Criteria

1. WHEN the Validator is invoked, THE Validator SHALL check every `DayCluster` in
   `state.day_clusters` for POI count; if any cluster exceeds `MAX_POIS_PER_DAY`, THE Validator
   SHALL add a descriptive error to `state.validation_errors`.
2. WHEN the Validator is invoked, THE Validator SHALL check every `DayCluster` for total
   duration; if any cluster's `total_duration_hours` exceeds `MAX_HOURS_PER_DAY`, THE Validator
   SHALL add a descriptive error to `state.validation_errors`.
3. WHEN the Validator is invoked, THE Validator SHALL check that lodging and POI price tiers are
   compatible with `state.constraints.budget`; if they are not, THE Validator SHALL add a
   descriptive budget error to `state.validation_errors`.
4. IF `state.validation_errors` is empty after all checks, THEN THE Validator SHALL set
   `state.status` to `"valid"`.
5. IF `state.validation_errors` is non-empty after all checks, THEN THE Validator SHALL set
   `state.status` to `"invalid"` and increment `state.retry_count` by 1.
6. THE Validator SHALL treat `state.status == "valid"` as equivalent to
   `state.validation_errors == []`; these two conditions SHALL always be consistent.

---

### Requirement 11: LangGraph Workflow — State Machine Orchestration

**User Story:** As a system architect, I want the agents to be orchestrated by a compiled state
machine, so that execution order, retry logic, and state transitions are explicit and auditable.

#### Acceptance Criteria

1. THE Workflow SHALL execute agent nodes in the fixed sequence: Coordinator → Researcher →
   Logistics_Agent → Validator → (conditionally) Compiler.
2. WHEN `state.status == "invalid"` and `state.retry_count < MAX_RETRIES`, THE Workflow SHALL
   route execution back to the Coordinator node for re-planning.
3. WHEN `state.status == "valid"`, THE Workflow SHALL route execution to the Compiler node.
4. THE Workflow SHALL invoke the Coordinator node at most `MAX_RETRIES + 1` times per request
   (initial invocation plus at most `MAX_RETRIES` re-plan cycles).
5. THE Workflow SHALL use a `MemorySaver` checkpointer during development; the checkpointer
   interface SHALL be swappable for a persistent backend in production.

---

### Requirement 12: Validation Loop Exhaustion Handling

**User Story:** As a client, I want to receive a partial result when the system cannot produce a
fully valid itinerary, so that I still have useful travel information.

#### Acceptance Criteria

1. IF `state.retry_count >= MAX_RETRIES` (where MAX_RETRIES = 3) and the Validator sets
   `state.status` to `"invalid"`, THEN THE Workflow SHALL route to the Compiler rather than
   returning to the Coordinator.
2. IF the itinerary is compiled after validation loop exhaustion, THEN THE API SHALL return
   HTTP 206 Partial Content with the itinerary compiled from the final retry state and a
   non-empty `warnings` field.
3. IF the itinerary is compiled after validation loop exhaustion, THEN THE Compiler SHALL
   populate `warnings` with all strings present in `state.validation_errors` at compilation
   time.
4. THE `ItineraryResponse` model SHALL include a `warnings` field of type `list[str]` with a
   default of `[]`, used to surface validation errors in partial-result responses.

---

### Requirement 13: Compiler Agent — Itinerary Synthesis

**User Story:** As a traveller, I want the system to produce a readable, well-structured
itinerary, so that I can follow it without needing to interpret raw data.

#### Acceptance Criteria

1. WHEN the Compiler is invoked with `state.status == "valid"`, THE Compiler SHALL call the
   OpenAI LLM with a prompt built from `state.constraints`, `state.day_clusters`,
   `state.lodging`, and `state.transit`.
2. THE Compiler SHALL parse the LLM response into a valid `ItineraryResponse` using strict
   Pydantic validation.
3. THE Compiler SHALL set `ItineraryResponse.generated_at` to the current UTC datetime.
4. THE `ItineraryResponse` produced by THE Compiler SHALL contain exactly `n_days` `DayPlan`
   objects, where `n_days` is taken from `state.constraints.n_days`.
5. WHEN the Compiler completes successfully, THE Compiler SHALL set `state.status` to `"done"`.

---

### Requirement 14: Budget Compatibility Rules

**User Story:** As a traveller on a fixed budget, I want the system to respect my budget level
strictly, so that I am not presented with options I cannot afford.

#### Acceptance Criteria

1. IF evaluating budget compatibility and a `POI` or `LodgingOption` has `price_tier == 1`,
   THEN THE Validator SHALL accept it for any `BudgetLevel`.
2. IF evaluating budget compatibility and `price_tier == 2`, THEN THE Validator SHALL accept it
   only for `BudgetLevel.MEDIUM`, `HIGH`, or `LUXURY`; otherwise add a budget error.
3. IF evaluating budget compatibility and `price_tier == 3`, THEN THE Validator SHALL accept it
   only for `BudgetLevel.HIGH` or `LUXURY`; otherwise add a budget error.
4. IF evaluating budget compatibility and `price_tier == 4`, THEN THE Validator SHALL accept it
   only for `BudgetLevel.LUXURY`; otherwise add a budget error.
5. A plan that passes budget validation at `BudgetLevel.LOW` SHALL also pass budget validation
   at `BudgetLevel.MEDIUM`, `BudgetLevel.HIGH`, and `BudgetLevel.LUXURY`.
6. IF a `POI` or `LodgingOption` has a `price_tier` value outside the range 1–4, THEN THE
   Validator SHALL add a descriptive error to `state.validation_errors`.

---

### Requirement 15: External API Error Handling

**User Story:** As an operator, I want the system to handle external API failures gracefully, so
that transient outages do not cause silent data corruption or unhandled exceptions.

#### Acceptance Criteria

1. WHEN an OpenAI API call returns a timeout or HTTP 429 response, THE System SHALL retry with
   exponential back-off and jitter for at most 3 attempts with a base delay of 1 second.
2. IF all OpenAI retry attempts are exhausted, THEN THE System SHALL propagate an `LLMError`
   which THE API SHALL translate to HTTP 503.
3. WHEN a Tavily search call fails transiently, THE Search_Tools SHALL apply the same retry
   policy (max 3 retries, exponential back-off, base delay 1 s).
4. IF a POI returned by any external source has `lat` or `lon` outside valid ranges, THEN THE
   System SHALL filter out that POI and log a warning before proceeding with the remaining
   valid POIs.
5. IF filtering invalid POIs reduces the valid POI count below `n_days`, THEN THE Logistics_Agent
   SHALL reduce `n_clusters` to match the available valid POI count.

---

### Requirement 16: Security and Input Safety

**User Story:** As an operator, I want the system to protect API keys and prevent prompt
injection, so that the service cannot be abused to leak secrets or manipulate LLM behaviour.

#### Acceptance Criteria

1. THE System SHALL load `OPENAI_API_KEY` and `TAVILY_API_KEY` exclusively from environment
   variables; these values SHALL never appear in source code, log output, or API responses.
2. THE Coordinator SHALL always pass user-supplied query text as a `HumanMessage`; it SHALL
   never be interpolated into the static system prompt.
3. THE API SHALL enforce a maximum query length of 500 characters via Pydantic validation before
   any LLM call is made.
4. THE System SHALL parse all LLM-generated JSON through strict Pydantic models; unexpected
   fields SHALL be ignored and required fields SHALL be type-checked before downstream use.
5. WHERE a rate-limiting middleware is configured, THE API SHALL apply it to the `POST /plan`
   endpoint to prevent LLM cost abuse.
