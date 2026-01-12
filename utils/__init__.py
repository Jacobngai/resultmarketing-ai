"""
Utilities package for ResultMarketing AI Microservice
"""
from .phone_formatter import (
    clean_phone_number,
    is_malaysian_number,
    format_malaysian_phone,
    validate_malaysian_phone,
    extract_phone_numbers,
    normalize_phone_for_comparison
)

from .context_manager import (
    estimate_tokens,
    manage_context_window,
    summarize_contacts,
    paginate_results,
    build_contact_context,
    extract_query_intent
)

__all__ = [
    "clean_phone_number",
    "is_malaysian_number",
    "format_malaysian_phone",
    "validate_malaysian_phone",
    "extract_phone_numbers",
    "normalize_phone_for_comparison",
    "estimate_tokens",
    "manage_context_window",
    "summarize_contacts",
    "paginate_results",
    "build_contact_context",
    "extract_query_intent"
]
