# Travel Planner API - Complete Testing Guide

## Quick Start

### 1. Import into Postman
- Open Postman
- Click "Import" 
- Select `.postman_collection.json` from this repo
- Collections should appear in your workspace

### 2. Set Base URL
Collections use `{{base_url}}` variable set to `http://localhost:8000`

Ensure server is running:
```bash
python -m uvicorn app.main:app --reload
```

---

## API Endpoints Overview

### Health & Status
```
GET /health          → Server status
GET /                → Frontend (HTML)
```

### Trip Planning
```
POST /api/plan              → Generate itinerary (auto-saves to database)
POST /api/export-pdf        → Download itinerary as PDF
GET  /api/itineraries/{dest}  → List all itineraries for destination
GET  /api/itinerary/{id}    → Retrieve specific saved itinerary
DELETE /api/itinerary/{id}  → Delete saved itinerary
```

---

## Test Scenarios

### ✅ Test 1: Basic Itinerary Generation
**Endpoint:** `POST /api/plan`
**Query:** `"india for 5 people"`
**Expected:** 
- Status: 200 OK
- Contains: `destination`, `n_days`, `days`, `total_estimated_cost`
- Database: Auto-saved

**Postman Test:**
```
pm.test("Status is 200", () => pm.response.code === 200);
pm.test("Has destination", () => pm.response.json().destination);
pm.test("Has itinerary days", () => pm.response.json().days.length > 0);
```

### ✅ Test 2: Multi-Language Support
**Endpoint:** `POST /api/plan?language=es`
**Query:** `"españa madrid barcelona"`
**Expected:** Response with Spanish context (parameter accepted)

### ✅ Test 3: PDF Export
**Endpoint:** `POST /api/export-pdf`
**Query:** `"japan 3 days"`
**Expected:**
- Status: 200
- Content-Type: `application/pdf`
- File downloadable

### ✅ Test 4: Database Persistence
**Step 1:** Generate itinerary
```json
POST /api/plan
{"query": "italy 4 days"}
```
Extract itinerary ID from response

**Step 2:** Retrieve it
```
GET /api/itinerary/{id}
```
Expected: Same itinerary data returned

**Step 3:** List by destination
```
GET /api/itineraries/Italy
```
Expected: Returns array with at least 1 itinerary

### ✅ Test 5: Error Handling
- Empty query → 422 error
- Invalid language parameter → Accepted (doesn't fail)
- Malformed JSON → 422 error
- Timeout (>120s) → 503 error

---

## Postman Collection Structure

```
Travel Planner API
├── Health & Status
│   ├── Health Check
│   └── Frontend
├── Trip Planning
│   ├── Generate Itinerary - India
│   ├── Generate Itinerary - Japan
│   └── Generate Itinerary - Europe Budget
├── Multi-Language Support
│   ├── Spanish - España
│   └── French - Paris
├── PDF Export
│   └── Export India Itinerary to PDF
├── Database - Retrieve Saved
│   ├── Get All India Itineraries
│   └── Get Specific Itinerary
└── Error Handling
    ├── Empty Query
    └── Invalid Language
```

---

## Example Requests

### Generate Itinerary
```bash
curl -X POST http://localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{
    "query": "thailand 5 days beach adventure",
    "preferences": ["beaches", "food", "culture"]
  }'
```

**Response (excerpt):**
```json
{
  "destination": "Thailand",
  "n_days": 5,
  "budget": "medium",
  "total_estimated_cost": 1500.0,
  "days": [
    {
      "day_number": 1,
      "theme": "Bangkok: Urban Exploration",
      "narrative": "...",
      "pois": [...]
    }
  ],
  "tips": "...",
  "warnings": {}
}
```

### Export PDF
```bash
curl -X POST http://localhost:8000/api/export-pdf \
  -H "Content-Type: application/json" \
  -d '{"query": "france 3 days"}' \
  --output france_itinerary.pdf
```

### Retrieve from Database
```bash
# List all India itineraries
curl http://localhost:8000/api/itineraries/India

# Get specific itinerary
curl http://localhost:8000/api/itinerary/550e8400-e29b-41d4-a716-446655440000
```

---

## Performance Benchmarks

| Endpoint | Avg Time | Max Time |
|----------|----------|----------|
| `/api/plan` | 15-20s | 30-40s (Gemini + Tavily) |
| `/api/export-pdf` | 20-25s | Same as /api/plan + PDF gen |
| `/api/itinerary/{id}` | <100ms | <500ms |
| `/api/itineraries/{dest}` | <100ms | <500ms |

---

## Environment Configuration

### Local (Development)
```json
{
  "base_url": "http://localhost:8000",
  "timeout": 150000,
  "retry": 0
}
```

### Production (When Deployed)
```json
{
  "base_url": "https://travel-planner.example.com",
  "timeout": 120000,
  "retry": 2
}
```

---

## Troubleshooting

### "TravelConstraints' object has no attribute 'get'"
**Cause:** Old coordinator version
**Fix:** Restart server with `--reload`

### "Unexpected error: Object of type datetime not JSON serializable"
**Cause:** Datetime serialization issue
**Fix:** Server will auto-reload with fix

### "Travel planning request timed out"
**Cause:** Gemini API slow or network latency
**Fix:** Increase timeout to 180s or check API keys

### Empty itinerary_id returned
**Cause:** Response schema doesn't include ID
**Expected:** ID saved to database but not in response (retrieve by destination)

---

## Automated Testing

### Run with Postman CLI
```bash
# Install Newman (Postman CLI)
npm install -g newman

# Run collection
newman run .postman_collection.json \
  --environment postman-env.json \
  --reporters cli,json
```

### Run with Shell Script
```bash
#!/bin/bash
BASE_URL="http://localhost:8000"

# Test health
curl -f $BASE_URL/health || exit 1

# Test plan
RESPONSE=$(curl -s -X POST $BASE_URL/api/plan \
  -H "Content-Type: application/json" \
  -d '{"query":"paris 3 days"}')

if echo $RESPONSE | grep -q "destination"; then
  echo "✓ API Tests Passed"
else
  echo "✗ API Tests Failed"
  exit 1
fi
```

---

## Integration Testing Checklist

- [ ] Server starts without errors
- [ ] Health endpoint returns 200
- [ ] Frontend loads (GET /)
- [ ] Basic itinerary generates (5-40s)
- [ ] PDF export works
- [ ] Itineraries save to database
- [ ] Retrieve from database works
- [ ] Multi-language parameter accepted
- [ ] Error handling (empty query) returns 422
- [ ] Performance within SLA (40s max)

---

## Next Steps

1. **Import collection into Postman**
2. **Set base_url to your deployment**
3. **Run tests before each release**
4. **Monitor response times**
5. **Add custom test scripts** for business logic

---

## Support

For issues:
1. Check server logs: `uvicorn app.main:app --reload`
2. Verify Gemini API key in `.env`
3. Verify Tavily API key in `.env`
4. Test with curl first, then Postman
