import os
from dotenv import load_dotenv

load_dotenv()

def _get_val(key: str, default: str = "") -> str:
    # 1. Check local environment (.env)
    val = os.getenv(key)
    if val:
        return val
    
    # 2. Check Streamlit Cloud Secrets (st.secrets)
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    
    return default

class Config:
    MONDAY_API_TOKEN = _get_val("MONDAY_API_TOKEN", "")
    MONDAY_API_URL = "https://api.monday.com/v2"
    
    MONDAY_DEALS_BOARD_ID = _get_val("MONDAY_DEALS_BOARD_ID", "")
    MONDAY_WORK_ORDERS_BOARD_ID = _get_val("MONDAY_WORK_ORDERS_BOARD_ID", "")
    
    GEMINI_API_KEY = _get_val("GEMINI_API_KEY", "")
    GROQ_API_KEY = _get_val("GROQ_API_KEY", "")
    
    CACHE_TTL_SECONDS = 300  # 5 minutes in-memory cache
