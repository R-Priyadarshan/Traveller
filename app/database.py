"""Database models and operations for saving travel itineraries."""

import json
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, Float, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel

# Database setup
DATABASE_URL = "sqlite:///./travel_planner.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ItineraryDB(Base):
    """Database model for saved itineraries."""
    __tablename__ = "itineraries"

    id = Column(String, primary_key=True)
    query = Column(String, index=True)
    destination = Column(String, index=True)
    n_days = Column(Integer)
    budget = Column(String)
    traveller_count = Column(Integer)
    language = Column(String, default="en")
    total_estimated_cost = Column(Float)
    itinerary_data = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SavedItinerarySchema(BaseModel):
    """Schema for API responses."""
    id: str
    destination: str
    n_days: int
    budget: str
    total_estimated_cost: float
    created_at: datetime

    class Config:
        from_attributes = True


# Create tables
Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_itinerary(db: Session, itinerary_id: str, query: str, destination: str, n_days: int, 
                   budget: str, traveller_count: int, language: str, total_cost: float, itinerary_data: dict) -> ItineraryDB:
    """Save itinerary to database."""
    db_item = ItineraryDB(
        id=itinerary_id,
        query=query,
        destination=destination,
        n_days=n_days,
        budget=budget,
        traveller_count=traveller_count,
        language=language,
        total_estimated_cost=total_cost,
        itinerary_data=json.dumps(itinerary_data)
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def get_itinerary(db: Session, itinerary_id: str) -> ItineraryDB:
    """Retrieve itinerary by ID."""
    return db.query(ItineraryDB).filter(ItineraryDB.id == itinerary_id).first()


def get_itineraries_by_destination(db: Session, destination: str, limit: int = 10):
    """Get all itineraries for a destination."""
    return db.query(ItineraryDB).filter(ItineraryDB.destination == destination).order_by(ItineraryDB.created_at.desc()).limit(limit).all()


def get_user_itineraries(db: Session, query: str, limit: int = 10):
    """Get all itineraries matching a search query."""
    return db.query(ItineraryDB).filter(ItineraryDB.query.ilike(f"%{query}%")).order_by(ItineraryDB.created_at.desc()).limit(limit).all()


def delete_itinerary(db: Session, itinerary_id: str) -> bool:
    """Delete an itinerary."""
    db_item = db.query(ItineraryDB).filter(ItineraryDB.id == itinerary_id).first()
    if db_item:
        db.delete(db_item)
        db.commit()
        return True
    return False
