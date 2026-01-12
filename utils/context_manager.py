"""
AI context window management utilities
"""
from typing import List, Dict, Any, Optional, Tuple
import json
from models.schemas import ContactData


# Approximate tokens per character (conservative estimate)
TOKENS_PER_CHAR = 0.25


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in a text string

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    return int(len(text) * TOKENS_PER_CHAR)


def manage_context_window(
    contacts: List[Dict[str, Any]],
    max_tokens: int = 4000,
    max_contacts: int = 50
) -> Tuple[List[Dict[str, Any]], bool, str]:
    """
    Manage context window by limiting contacts if needed

    Args:
        contacts: List of contact dictionaries
        max_tokens: Maximum tokens allowed in context
        max_contacts: Maximum number of contacts to include

    Returns:
        Tuple of (limited_contacts, was_truncated, summary_message)
    """
    if not contacts:
        return [], False, ""

    total_contacts = len(contacts)

    # First limit by count
    limited_contacts = contacts[:max_contacts]

    # Then check token limit
    context_text = json.dumps(limited_contacts, default=str)
    estimated_tokens = estimate_tokens(context_text)

    # If still over token limit, reduce further
    while estimated_tokens > max_tokens and len(limited_contacts) > 10:
        limited_contacts = limited_contacts[:len(limited_contacts) - 10]
        context_text = json.dumps(limited_contacts, default=str)
        estimated_tokens = estimate_tokens(context_text)

    was_truncated = len(limited_contacts) < total_contacts

    if was_truncated:
        summary_message = (
            f"Showing {len(limited_contacts)} of {total_contacts} contacts. "
            f"Use specific search queries to find other contacts."
        )
    else:
        summary_message = ""

    return limited_contacts, was_truncated, summary_message


def summarize_contacts(
    contacts: List[Dict[str, Any]],
    max_summary_length: int = 500
) -> str:
    """
    Create a summary of contacts for AI context

    Args:
        contacts: List of contact dictionaries
        max_summary_length: Maximum length of summary

    Returns:
        Summary string
    """
    if not contacts:
        return "No contacts available."

    total = len(contacts)

    # Count by category/industry if available
    categories = {}
    industries = {}

    for contact in contacts:
        cat = contact.get("category", "unknown")
        ind = contact.get("industry", "unknown")

        categories[cat] = categories.get(cat, 0) + 1
        if ind and ind != "unknown":
            industries[ind] = industries.get(ind, 0) + 1

    # Build summary
    summary_parts = [f"Total contacts: {total}"]

    if categories:
        cat_summary = ", ".join([f"{k}: {v}" for k, v in sorted(categories.items(), key=lambda x: -x[1])[:5]])
        summary_parts.append(f"By category: {cat_summary}")

    if industries:
        ind_summary = ", ".join([f"{k}: {v}" for k, v in sorted(industries.items(), key=lambda x: -x[1])[:5]])
        summary_parts.append(f"By industry: {ind_summary}")

    # Add sample names
    sample_names = [c.get("name", "Unknown") for c in contacts[:5] if c.get("name")]
    if sample_names:
        summary_parts.append(f"Sample contacts: {', '.join(sample_names)}")

    summary = " | ".join(summary_parts)

    # Truncate if too long
    if len(summary) > max_summary_length:
        summary = summary[:max_summary_length - 3] + "..."

    return summary


def paginate_results(
    items: List[Any],
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[Any], Dict[str, Any]]:
    """
    Paginate a list of items

    Args:
        items: List of items to paginate
        page: Page number (1-indexed)
        page_size: Number of items per page

    Returns:
        Tuple of (page_items, pagination_info)
    """
    total_items = len(items)
    total_pages = (total_items + page_size - 1) // page_size

    # Ensure valid page number
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1

    # Calculate slice indices
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    page_items = items[start_idx:end_idx]

    pagination_info = {
        "current_page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_previous": page > 1,
        "has_next": page < total_pages,
        "start_index": start_idx + 1 if page_items else 0,
        "end_index": min(end_idx, total_items)
    }

    return page_items, pagination_info


def build_contact_context(
    contacts: List[Dict[str, Any]],
    query: str,
    max_tokens: int = 4000
) -> str:
    """
    Build optimized context string for AI queries about contacts

    Args:
        contacts: List of contact dictionaries
        query: User's query to help prioritize relevant contacts
        max_tokens: Maximum tokens for context

    Returns:
        Formatted context string
    """
    if not contacts:
        return "No contacts in the system yet."

    # Filter and limit contacts
    limited_contacts, was_truncated, summary = manage_context_window(
        contacts, max_tokens, max_contacts=50
    )

    # Build context
    context_parts = []

    # Add summary if truncated
    if was_truncated:
        context_parts.append(f"[{summary}]")
        context_parts.append("")

    # Format contacts
    context_parts.append("Available contacts:")
    for i, contact in enumerate(limited_contacts, 1):
        name = contact.get("name", "Unknown")
        company = contact.get("company", "")
        phone = contact.get("phone", "")
        email = contact.get("email", "")

        contact_line = f"{i}. {name}"
        if company:
            contact_line += f" ({company})"
        if phone:
            contact_line += f" - {phone}"
        if email:
            contact_line += f" - {email}"

        context_parts.append(contact_line)

    return "\n".join(context_parts)


def extract_query_intent(query: str) -> Dict[str, Any]:
    """
    Extract intent and parameters from user query

    Args:
        query: User's query string

    Returns:
        Dictionary with intent and extracted parameters
    """
    query_lower = query.lower()

    intent = {
        "type": "general",
        "action": None,
        "filters": {},
        "search_terms": []
    }

    # Detect query type
    if any(word in query_lower for word in ["find", "search", "look for", "show me", "who is", "get"]):
        intent["type"] = "contact_lookup"
        intent["action"] = "search"
    elif any(word in query_lower for word in ["how many", "count", "total", "statistics", "analytics"]):
        intent["type"] = "analytics"
        intent["action"] = "count"
    elif any(word in query_lower for word in ["follow up", "remind", "schedule", "contact today"]):
        intent["type"] = "followup"
        intent["action"] = "list"
    elif any(word in query_lower for word in ["add", "create", "new contact"]):
        intent["type"] = "create"
        intent["action"] = "add"
    elif any(word in query_lower for word in ["update", "change", "edit", "modify"]):
        intent["type"] = "update"
        intent["action"] = "edit"
    elif any(word in query_lower for word in ["delete", "remove"]):
        intent["type"] = "delete"
        intent["action"] = "remove"

    # Extract potential filters
    if "from" in query_lower and "company" in query_lower:
        intent["filters"]["has_company"] = True

    if any(ind in query_lower for ind in ["tech", "finance", "healthcare", "retail", "manufacturing"]):
        for ind in ["tech", "finance", "healthcare", "retail", "manufacturing"]:
            if ind in query_lower:
                intent["filters"]["industry"] = ind
                break

    return intent
