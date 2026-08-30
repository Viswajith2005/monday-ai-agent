import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN", "")
    MONDAY_API_URL = "https://api.monday.com/v2"
    
    MONDAY_DEALS_BOARD_ID = os.getenv("MONDAY_DEALS_BOARD_ID", "")
    MONDAY_WORK_ORDERS_BOARD_ID = os.getenv("MONDAY_WORK_ORDERS_BOARD_ID", "")
    
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    
    CACHE_TTL_SECONDS = 300  # 5 minutes in-memory cache
