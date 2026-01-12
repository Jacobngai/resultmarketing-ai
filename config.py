"""
Configuration settings for ResultMarketing AI Microservice
"""
import os
from typing import List
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # API Configuration
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Anthropic Claude Configuration
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-3-sonnet-20240229")

    # OpenAI Configuration (backup/voice)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4-turbo")

    # Google Cloud Vision
    google_credentials_path: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    google_project_id: str = os.getenv("GOOGLE_PROJECT_ID", "")

    # Redis Configuration
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # CORS Settings
    cors_origins: List[str] = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173"
    ).split(",")

    # Rate Limiting
    rate_limit_requests: int = int(os.getenv("RATE_LIMIT_REQUESTS", "50"))
    rate_limit_window: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

    # Context Management
    max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS", "4000"))
    max_contacts_in_context: int = int(os.getenv("MAX_CONTACTS_IN_CONTEXT", "50"))

    # Malaysian Sales Context System Prompt
    system_prompt: str = """You are an AI assistant for ResultMarketing CRM, designed specifically for Malaysian sales professionals.

Your role is to:
1. Help users manage their contacts and client relationships
2. Analyze spreadsheets and extract contact information
3. Process business cards and namecards
4. Provide insights about follow-up timing and sales strategies
5. Answer questions about their contacts and pipeline

Key context about Malaysian business culture:
- Business relationships are built on trust and personal connections (guanxi)
- Formal titles are important (Dato', Tan Sri, Dr., etc.)
- Multiple languages may appear: English, Bahasa Malaysia, Chinese
- Phone numbers typically start with +60 (country code)
- Common mobile prefixes: 010, 011, 012, 013, 014, 016, 017, 018, 019
- Business hours: Monday-Friday, some companies work Saturday morning
- Key holidays: Chinese New Year, Hari Raya, Deepavali affect follow-up timing

Always be helpful, professional, and culturally aware. Provide actionable insights for improving sales relationships."""

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()


# Column mapping configuration for spreadsheet processing
COLUMN_MAPPINGS = {
    "name": ["name", "full name", "contact name", "client name", "nama", "customer name", "prospect name"],
    "phone": ["phone", "mobile", "tel", "telephone", "handphone", "hp", "contact number", "phone number", "no tel", "no telefon"],
    "email": ["email", "e-mail", "email address", "emel"],
    "company": ["company", "organization", "organisation", "syarikat", "business", "firm", "company name"],
    "title": ["title", "position", "designation", "role", "job title", "jawatan"],
    "industry": ["industry", "sector", "industri", "business type"],
    "address": ["address", "alamat", "location", "office address"],
    "notes": ["notes", "remarks", "comments", "catatan", "description"],
    "source": ["source", "lead source", "referral", "sumber"],
    "status": ["status", "lead status", "stage", "pipeline stage"]
}

# Phone number patterns for Malaysian numbers
MALAYSIAN_PHONE_PATTERNS = {
    "mobile_prefixes": ["010", "011", "012", "013", "014", "016", "017", "018", "019"],
    "landline_prefixes": ["03", "04", "05", "06", "07", "08", "09"],
    "country_code": "+60"
}

# OCR confidence thresholds
OCR_CONFIDENCE_THRESHOLDS = {
    "high": 0.9,
    "medium": 0.7,
    "low": 0.5
}
