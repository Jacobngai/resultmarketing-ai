"""
Malaysian phone number formatting utilities
"""
import re
from typing import Optional, Tuple


# Malaysian mobile prefixes (after country code)
MOBILE_PREFIXES = ["10", "11", "12", "13", "14", "16", "17", "18", "19"]

# Malaysian landline prefixes (area codes)
LANDLINE_PREFIXES = ["3", "4", "5", "6", "7", "8", "9"]

# Country code
COUNTRY_CODE = "60"


def clean_phone_number(phone: str) -> str:
    """
    Remove all non-digit characters from phone number except leading +

    Args:
        phone: Raw phone number string

    Returns:
        Cleaned phone number with only digits (and optional leading +)
    """
    if not phone:
        return ""

    # Preserve leading + if present
    has_plus = phone.strip().startswith("+")

    # Remove all non-digit characters
    cleaned = re.sub(r"[^\d]", "", phone)

    # Add back the + if it was present
    if has_plus:
        cleaned = "+" + cleaned

    return cleaned


def is_malaysian_number(phone: str) -> bool:
    """
    Check if phone number is a Malaysian number

    Args:
        phone: Phone number to check

    Returns:
        True if Malaysian number, False otherwise
    """
    cleaned = clean_phone_number(phone).lstrip("+")

    # Check if starts with Malaysian country code
    if cleaned.startswith("60"):
        return True

    # Check if starts with 0 (local format)
    if cleaned.startswith("0"):
        remaining = cleaned[1:]
        # Check mobile prefixes
        for prefix in MOBILE_PREFIXES:
            if remaining.startswith(prefix):
                return True
        # Check landline prefixes
        for prefix in LANDLINE_PREFIXES:
            if remaining.startswith(prefix):
                return True

    # Check direct mobile/landline without leading 0 or country code
    for prefix in MOBILE_PREFIXES:
        if cleaned.startswith(prefix):
            return True

    return False


def format_malaysian_phone(phone: str, include_country_code: bool = True) -> Optional[str]:
    """
    Format a Malaysian phone number to standard format

    Args:
        phone: Raw phone number
        include_country_code: Whether to include +60 prefix

    Returns:
        Formatted phone number or None if invalid
    """
    if not phone:
        return None

    cleaned = clean_phone_number(phone).lstrip("+")

    # Remove country code if present
    if cleaned.startswith("60"):
        cleaned = cleaned[2:]

    # Remove leading 0 if present
    if cleaned.startswith("0"):
        cleaned = cleaned[1:]

    # Validate length (8-10 digits after removing prefix)
    if len(cleaned) < 8 or len(cleaned) > 10:
        return None

    # Determine if mobile or landline and format accordingly
    is_mobile = any(cleaned.startswith(prefix) for prefix in MOBILE_PREFIXES)
    is_landline = any(cleaned.startswith(prefix) for prefix in LANDLINE_PREFIXES)

    if not is_mobile and not is_landline:
        return None

    if include_country_code:
        # Format: +60 XX-XXX XXXX or +60 X-XXXX XXXX
        if is_mobile:
            # Mobile: +60 12-345 6789
            if len(cleaned) >= 9:
                formatted = f"+60 {cleaned[:2]}-{cleaned[2:5]} {cleaned[5:]}"
            else:
                formatted = f"+60 {cleaned[:2]}-{cleaned[2:]}"
        else:
            # Landline: +60 3-1234 5678
            if len(cleaned) >= 8:
                formatted = f"+60 {cleaned[:1]}-{cleaned[1:5]} {cleaned[5:]}"
            else:
                formatted = f"+60 {cleaned[:1]}-{cleaned[1:]}"
    else:
        # Local format: 012-345 6789 or 03-1234 5678
        if is_mobile:
            if len(cleaned) >= 9:
                formatted = f"0{cleaned[:2]}-{cleaned[2:5]} {cleaned[5:]}"
            else:
                formatted = f"0{cleaned[:2]}-{cleaned[2:]}"
        else:
            if len(cleaned) >= 8:
                formatted = f"0{cleaned[:1]}-{cleaned[1:5]} {cleaned[5:]}"
            else:
                formatted = f"0{cleaned[:1]}-{cleaned[1:]}"

    return formatted


def validate_malaysian_phone(phone: str) -> Tuple[bool, str]:
    """
    Validate a Malaysian phone number

    Args:
        phone: Phone number to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if not phone:
        return False, "Phone number is empty"

    cleaned = clean_phone_number(phone).lstrip("+")

    # Remove country code if present
    if cleaned.startswith("60"):
        cleaned = cleaned[2:]

    # Remove leading 0 if present
    if cleaned.startswith("0"):
        cleaned = cleaned[1:]

    # Check length
    if len(cleaned) < 8:
        return False, "Phone number is too short"

    if len(cleaned) > 10:
        return False, "Phone number is too long"

    # Check prefix
    is_mobile = any(cleaned.startswith(prefix) for prefix in MOBILE_PREFIXES)
    is_landline = any(cleaned.startswith(prefix) for prefix in LANDLINE_PREFIXES)

    if not is_mobile and not is_landline:
        return False, f"Invalid Malaysian phone prefix. Mobile should start with {', '.join(MOBILE_PREFIXES)}"

    return True, "Valid Malaysian phone number"


def extract_phone_numbers(text: str) -> list:
    """
    Extract all potential phone numbers from text

    Args:
        text: Text to search for phone numbers

    Returns:
        List of extracted phone numbers
    """
    if not text:
        return []

    # Pattern to match various phone number formats
    patterns = [
        r"\+60[\s\-]?\d{1,2}[\s\-]?\d{3,4}[\s\-]?\d{4}",  # +60 format
        r"0\d{1,2}[\s\-]?\d{3,4}[\s\-]?\d{4}",            # Local format with 0
        r"\d{9,12}",                                        # Plain digits
    ]

    phone_numbers = []

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            cleaned = clean_phone_number(match)
            if is_malaysian_number(cleaned) and cleaned not in phone_numbers:
                phone_numbers.append(cleaned)

    return phone_numbers


def normalize_phone_for_comparison(phone: str) -> str:
    """
    Normalize phone number for duplicate comparison

    Args:
        phone: Phone number to normalize

    Returns:
        Normalized phone number (just digits, with country code)
    """
    if not phone:
        return ""

    cleaned = clean_phone_number(phone).lstrip("+")

    # Add country code if not present
    if not cleaned.startswith("60"):
        if cleaned.startswith("0"):
            cleaned = "60" + cleaned[1:]
        else:
            cleaned = "60" + cleaned

    return cleaned
