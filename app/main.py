"""FastAPI entry point for the Travel Planner."""

from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import os
from io import BytesIO
import uuid

from app.schemas import TravelRequest, ItineraryResponse, initial_state
from app.exceptions import ConstraintExtractionError, LLMError, SearchError
from app.workflow import build_graph
from app.tools.search import _clear_cache
from app.database import (
    get_db, save_itinerary, get_itinerary, 
    get_itineraries_by_destination, delete_itinerary,
    SavedItinerarySchema
)
from sqlalchemy.orm import Session

app = FastAPI(
    title="Travel Planner",
    description="Multi-agent AI system for travel itinerary planning",
    version="0.1.0",
)

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Build and cache the workflow graph
_graph = None


def get_graph():
    """Get or build the compiled workflow graph."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


@app.get("/")
async def root():
    """Serve the frontend."""
    static_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(static_file):
        return FileResponse(static_file)
    return {"message": "Travel Planner API"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/plan", response_model=ItineraryResponse)
@app.post("/api/plan", response_model=ItineraryResponse)
async def plan_trip(request: TravelRequest, language: str = Query("en"), save: bool = Query(True), db: Session = Depends(get_db)) -> ItineraryResponse:
    """
    Plan a trip based on user request.
    
    Query parameters:
    - language: Language for response ("en", "es", "fr", "de", "it", "ja", "zh")
    - save: Whether to save itinerary to database (default: True)

    Returns:
        - 200: Valid complete itinerary
        - 206: Partial itinerary (validation loop exhausted)
        - 422: Invalid request
        - 503: External API failure
    """
    try:
        # Validate request (Pydantic will handle this, but explicit here for clarity)
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=422, detail="query must be non-empty")

        # Clear search cache for this invocation
        _clear_cache()

        # Initialize state with language preference
        state = initial_state(request.query, request.preferences)
        state["language"] = language

        # Run workflow with timeout
        graph = get_graph()

        # Execute workflow synchronously
        final_state = None
        try:
            # Use a timeout wrapper with config for checkpointer
            loop = asyncio.get_event_loop()
            final_state = await asyncio.wait_for(
                loop.run_in_executor(None, _run_graph, graph, state),
                timeout=120.0,  # Increased timeout for Gemini + Tavily
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=503, detail="Travel planning request timed out")

        # Check final state
        if final_state["status"] == "error":
            errors = final_state.get("validation_errors", ["Unknown error"])
            raise HTTPException(status_code=422, detail=f"Planning failed: {errors[0]}")

        if final_state["itinerary"] is None:
            raise HTTPException(status_code=503, detail="Failed to generate itinerary")

        # Return based on validation status
        response = final_state["itinerary"]
        
        # Save to database if requested
        if save:
            itinerary_id = str(uuid.uuid4())
            constraints = final_state.get("constraints")
            budget = constraints.budget if constraints else "medium"
            traveller_count = constraints.traveller_count if constraints else 1
            save_itinerary(
                db,
                itinerary_id=itinerary_id,
                query=request.query,
                destination=response.destination,
                n_days=response.n_days,
                budget=budget,
                traveller_count=traveller_count,
                language=language,
                total_cost=response.total_estimated_cost,
                itinerary_data=response.model_dump(mode="json")  # Ensure JSON serializable
            )

        # Set status code based on partial vs. complete
        if final_state.get("retry_count", 0) >= 3 and final_state["status"] == "done":
            # Partial result after exhaustion
            return JSONResponse(
                status_code=206,
                content=response.model_dump(mode="json"),
            )

        return response

    except HTTPException:
        raise
    except ConstraintExtractionError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse request: {str(e)}",
        )
    except (SearchError, LLMError) as e:
        raise HTTPException(
            status_code=503,
            detail=f"External service failure: {str(e)}",
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.post("/api/export-pdf")
async def export_pdf(request: TravelRequest, language: str = Query("en")):
    """
    Generate and export itinerary as PDF.
    
    Returns: PDF file download
    """
    try:
        # First generate the itinerary
        loop = asyncio.get_event_loop()
        
        state = initial_state(request.query, request.preferences)
        state["language"] = language
        
        graph = get_graph()
        final_state = await asyncio.wait_for(
            loop.run_in_executor(None, _run_graph, graph, state),
            timeout=120.0,
        )
        
        if final_state["itinerary"] is None:
            raise HTTPException(status_code=503, detail="Failed to generate itinerary")
        
        # Generate PDF
        itinerary = final_state["itinerary"]
        pdf_buffer = generate_pdf(itinerary, language)
        
        return FileResponse(
            BytesIO(pdf_buffer),
            media_type="application/pdf",
            filename=f"{itinerary.destination}_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


def generate_pdf(itinerary: ItineraryResponse, language: str = "en") -> bytes:
    """Generate PDF from itinerary."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#6366f1'))
    
    # Title
    title = f"{itinerary.destination} - {itinerary.n_days} Days"
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Cost estimate
    story.append(Paragraph(f"<b>Estimated Cost:</b> ${itinerary.total_estimated_cost}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Days
    for day in itinerary.days:
        story.append(Paragraph(f"<b>Day {day['day_number']}: {day['theme']}</b>", styles['Heading2']))
        story.append(Paragraph(day['narrative'], styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
    
    # Tips
    if itinerary.tips:
        story.append(PageBreak())
        story.append(Paragraph("<b>Tips & Recommendations:</b>", styles['Heading2']))
        story.append(Paragraph(itinerary.tips, styles['Normal']))
    
    doc.build(story)
    return buffer.getvalue()


def _run_graph(graph, state):
    """Run the graph synchronously (wrapper for executor)."""
    # Checkpointer requires thread_id configuration
    config = {"configurable": {"thread_id": "default"}}
    final = graph.invoke(state, config=config)
    return final


@app.get("/api/itineraries/{destination}")
async def get_destination_itineraries(destination: str, db: Session = Depends(get_db)):
    """Get all saved itineraries for a destination."""
    itineraries = get_itineraries_by_destination(db, destination, limit=10)
    return {
        "destination": destination,
        "count": len(itineraries),
        "itineraries": [
            {
                "id": it.id,
                "n_days": it.n_days,
                "budget": it.budget,
                "cost": it.total_estimated_cost,
                "created_at": it.created_at
            }
            for it in itineraries
        ]
    }


@app.get("/api/itinerary/{itinerary_id}")
async def get_saved_itinerary(itinerary_id: str, db: Session = Depends(get_db)):
    """Retrieve a saved itinerary by ID."""
    itinerary = get_itinerary(db, itinerary_id)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    
    import json
    return {
        "id": itinerary.id,
        "destination": itinerary.destination,
        "n_days": itinerary.n_days,
        "budget": itinerary.budget,
        "query": itinerary.query,
        "language": itinerary.language,
        "total_cost": itinerary.total_estimated_cost,
        "itinerary": json.loads(itinerary.itinerary_data),
        "created_at": itinerary.created_at
    }


@app.delete("/api/itinerary/{itinerary_id}")
async def delete_saved_itinerary(itinerary_id: str, db: Session = Depends(get_db)):
    """Delete a saved itinerary."""
    success = delete_itinerary(db, itinerary_id)
    if not success:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return {"message": "Itinerary deleted"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
