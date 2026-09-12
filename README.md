# Travel Planner — Multi-Agent AI Itinerary System

A sophisticated multi-agent AI system that transforms natural-language travel requests into detailed, day-by-day itineraries using LangGraph, OpenAI, and Tavily search.

## Quick Start

### 1. Environment Setup

```bash
# Create and populate .env with your API keys
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
```

### 2. Install Dependencies

```bash
pip install -e .
```

### 3. Run the API

```bash
python -m uvicorn app.main:app --reload
```

Open http://localhost:8000/docs for interactive API docs.

### 4. Example Request

```bash
curl -X POST http://localhost:8000/plan \
  -H "Content-Type: application/json" \
  -d '{
    "query": "3 days in Paris for two people interested in art museums and cafes",
    "preferences": ["art", "museums", "food"],
    "budget": "medium"
  }'
```

Response (HTTP 200 with complete itinerary):
```json
{
  "destination": "Paris",
  "n_days": 3,
  "days": [
    {
      "day_number": 1,
      "theme": "Iconic Museums",
      "narrative": "Start with the Louvre...",
      "pois": [...],
      "estimated_walking_km": 5.2
    },
    ...
  ],
  "lodging": [...],
  "transit": [...],
  "warnings": [],
  "generated_at": "2026-09-11T14:30:45.123Z"
}
```

## Architecture

### Five-Agent Workflow

1. **Coordinator**: Parses free-text query → structured constraints
2. **Researcher**: Discovers & ranks POIs using Tavily + LLM
3. **Logistics**: Plans lodging, transit, geo-optimized daily routes
4. **Validator**: Enforces business rules (budget, capacity, duration)
5. **Compiler**: Synthesizes human-readable itinerary via LLM

### Workflow Features

- **Intelligent Retry Loop**: Validator can route back to Coordinator up to 3 times (MAX_RETRIES)
- **Partial Results**: HTTP 206 on loop exhaustion with validation warnings
- **Geo-Optimization**: K-Means clustering + nearest-neighbour Haversine routing per day
- **Resilient APIs**: Exponential backoff with jitter for OpenAI and Tavily calls

## API Endpoints

### `GET /health`
Health check returning `{"status": "ok"}`.

### `POST /plan`
**Request**: `TravelRequest` with:
- `query` (str, max 500 chars): Travel intent in natural language
- `preferences` (list[str], max 10): Activity interests
- `budget` (enum: LOW/MEDIUM/HIGH/LUXURY, default MEDIUM)
- `start_date` (optional date, must be today or future)
- `end_date` (optional date, must be after start_date)

**Response**:
- **200**: Complete valid itinerary (`ItineraryResponse`)
- **206**: Partial itinerary after validation loop exhaustion (includes `warnings`)
- **422**: Invalid request or constraint extraction failure
- **503**: External API failure (OpenAI, Tavily)

## Configuration

Environment variables (required):
- `OPENAI_API_KEY`: OpenAI API key
- `TAVILY_API_KEY`: Tavily search API key

Optional:
- `MAX_RETRIES`: Validation loop retries (default 3)
- `MAX_POIS_PER_DAY`: POIs per day constraint (default 5)
- `MAX_HOURS_PER_DAY`: Activity hours per day constraint (default 10)
- `MAX_POIS_TOTAL`: Total POIs to discover (default 30)

## Documentation

- **Design Document**: `.kiro/specs/travel-planner/design.md` — Architecture, algorithms, data models
- **Requirements**: `.kiro/specs/travel-planner/requirements.md` — 16 EARS-compliant requirements
- **Implementation Tasks**: `.kiro/specs/travel-planner/tasks.md` — 20 tasks with dependency graph

## Project Structure

```
app/
├── config.py           # Configuration & environment loader
├── exceptions.py       # Custom exceptions (LLMError, SearchError, ConstraintExtractionError)
├── main.py            # FastAPI entry point
├── schemas/           # Pydantic models (TravelRequest, POI, ItineraryResponse, etc.)
├── tools/             # Geo tools (Haversine, K-Means) & search tools (Tavily wrapper)
├── agents/            # Five agents (Coordinator, Researcher, Logistics, Validator, Compiler)
└── workflow/          # LangGraph state machine assembly
```

## Key Features

### Robust Error Handling
- Exponential backoff with jitter for external APIs (3 retries max)
- Structured error responses with HTTP status codes
- Graceful degradation with partial results

### Security
- API keys loaded from environment variables only
- Input validation (500 char limit on query, coordinate ranges, etc.)
- Static LLM system prompts (no user interpolation)

### Performance
- Per-invocation search result caching
- Concurrent batch search execution
- K-Means clustering optimized with scikit-learn
- Nearest-neighbour Haversine routing per day

### Extensibility
- Clean separation of concerns (schemas, tools, agents, workflow)
- Plugin-friendly agent architecture
- Swappable LLM and search backends

## Testing

```bash
# Run unit tests (when implemented)
pytest tests/

# Run with coverage
pytest --cov=app tests/

# Run integration tests only
pytest -m integration
```

## Deployment

For production:

1. **Swap MemorySaver** for persistent checkpointer (Redis/PostgreSQL)
2. **Add rate limiting** (slowapi or similar)
3. **Configure CORS** as needed
4. **Enable request logging** and monitoring
5. **Run behind reverse proxy** (nginx, cloudflare, etc.)

```bash
# Production deployment example
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

## Troubleshooting

**"OPENAI_API_KEY not found"**
- Ensure `.env` file exists with valid key
- Or set environment variable: `export OPENAI_API_KEY=sk-...`

**"No POIs found for destination"**
- Try more specific destination names
- Check Tavily API quota
- Verify internet connectivity

**Timeout errors (HTTP 503)**
- Check OpenAI/Tavily API status
- Increase timeout if needed
- Verify API keys are valid

## License

MIT

## Support

For issues, check:
1. `.env` configuration
2. API key validity at OpenAI and Tavily dashboards
3. Network connectivity
4. API rate limits and quotas

---

**Built with**: FastAPI, LangGraph, Pydantic, scikit-learn, OpenAI, Tavily
