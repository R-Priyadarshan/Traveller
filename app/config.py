"""Configuration loader for environment variables and constants."""

import os
from dotenv import load_dotenv

load_dotenv()

# API Keys (required at startup)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is required")
if not TAVILY_API_KEY:
    raise RuntimeError("TAVILY_API_KEY environment variable is required")

# Configuration constants
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
MAX_POIS_PER_DAY = int(os.getenv("MAX_POIS_PER_DAY", "5"))
MAX_HOURS_PER_DAY = float(os.getenv("MAX_HOURS_PER_DAY", "10"))
MAX_POIS_TOTAL = int(os.getenv("MAX_POIS_TOTAL", "30"))

__all__ = [
    "GEMINI_API_KEY",
    "TAVILY_API_KEY",
    "MAX_RETRIES",
    "MAX_POIS_PER_DAY",
    "MAX_HOURS_PER_DAY",
    "MAX_POIS_TOTAL",
]
