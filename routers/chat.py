"""
AI Chat processing endpoints
"""
import time
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.schemas import (
    ChatMessage,
    ChatQueryRequest,
    ChatQueryResponse,
    ChatRole,
    ProcessingStatus,
    APIResponse
)
from services.claude_service import claude_service
from utils.context_manager import (
    build_contact_context,
    extract_query_intent,
    paginate_results,
    summarize_contacts
)


router = APIRouter(prefix="/api/chat", tags=["Chat"])


class QueryRequest(BaseModel):
    """Simplified query request"""
    query: str
    conversation_history: Optional[List[Dict[str, str]]] = None
    contacts: Optional[List[Dict[str, Any]]] = None
    user_id: Optional[str] = None
    include_suggestions: bool = True


class AnalyticsQueryRequest(BaseModel):
    """Request for analytics-focused queries"""
    query: str
    contacts: List[Dict[str, Any]]
    date_range: Optional[Dict[str, str]] = None


@router.post("/query", response_model=APIResponse)
async def process_chat_query(request: QueryRequest):
    """
    Process a user query with Claude AI

    Handles:
    - Contact lookups and searches
    - Analytics questions
    - General CRM questions
    - Follow-up suggestions

    Automatically manages context window for large contact lists
    """
    start_time = time.time()

    try:
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        # Extract query intent
        intent = extract_query_intent(request.query)

        # Build contact context if contacts provided
        contact_context = None
        if request.contacts:
            contact_context = build_contact_context(
                request.contacts,
                request.query,
                max_tokens=4000
            )

        # Format conversation history
        formatted_history = None
        if request.conversation_history:
            formatted_history = [
                {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                }
                for msg in request.conversation_history[-10:]  # Last 10 messages
            ]

        # Send to Claude
        response_text, input_tokens, output_tokens = claude_service.chat_with_context(
            user_message=request.query,
            conversation_history=formatted_history,
            contact_context=contact_context,
            max_tokens=1024
        )

        # Generate suggested actions if requested
        suggested_actions = []
        if request.include_suggestions:
            suggested_actions = _generate_suggestions(intent, response_text)

        # Find referenced contacts in response
        referenced_contacts = []
        if request.contacts:
            for contact in request.contacts[:50]:
                name = contact.get("name", "")
                if name and name.lower() in response_text.lower():
                    referenced_contacts.append(contact.get("id", name))

        processing_time = int((time.time() - start_time) * 1000)

        result = ChatQueryResponse(
            response=response_text,
            query_type=intent["type"],
            referenced_contacts=referenced_contacts[:10],
            suggested_actions=suggested_actions,
            processing_time_ms=processing_time,
            tokens_used=input_tokens + output_tokens,
            status=ProcessingStatus.COMPLETED
        )

        return APIResponse(
            success=True,
            data=result.model_dump()
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analytics", response_model=APIResponse)
async def process_analytics_query(request: AnalyticsQueryRequest):
    """
    Process analytics-focused queries about contacts

    Provides:
    - Contact statistics
    - Industry breakdowns
    - Follow-up analysis
    - Pipeline insights
    """
    start_time = time.time()

    try:
        if not request.contacts:
            return APIResponse(
                success=True,
                data={
                    "response": "No contacts available to analyze.",
                    "analytics": {}
                }
            )

        # Calculate basic analytics
        analytics = _calculate_analytics(request.contacts)

        # Build analytics context
        analytics_context = f"""Analytics about user's contacts:

Total contacts: {analytics['total']}
By category: {analytics['by_category']}
By industry: {analytics['by_industry']}
With phone: {analytics['with_phone']}
With email: {analytics['with_email']}
Recent additions (last 30 days): {analytics.get('recent', 0)}

User's question: {request.query}

Provide helpful insights and answer the question based on this data."""

        # Get AI response
        response_text, input_tokens, output_tokens = claude_service.chat_with_context(
            user_message=analytics_context,
            max_tokens=1024
        )

        return APIResponse(
            success=True,
            data={
                "response": response_text,
                "analytics": analytics,
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "tokens_used": input_tokens + output_tokens
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggest-followup", response_model=APIResponse)
async def suggest_followup(
    contact: Dict[str, Any],
    interaction_history: Optional[List[Dict[str, Any]]] = None
):
    """
    Get AI-powered follow-up suggestions for a specific contact

    Considers:
    - Contact's industry and company type
    - Previous interaction history
    - Malaysian business culture
    - Optimal timing
    """
    try:
        if not contact:
            raise HTTPException(status_code=400, detail="Contact data required")

        suggestions = claude_service.generate_follow_up_suggestions(
            contact=contact,
            interaction_history=interaction_history
        )

        if suggestions.get("parse_error"):
            # Fallback to default suggestions
            suggestions = {
                "recommended_follow_up_days": 7,
                "best_contact_time": "morning",
                "suggested_approach": "email",
                "message_template": f"Hi {contact.get('name', 'there')}, I hope this message finds you well. I wanted to follow up on our previous conversation...",
                "reasoning": "Standard follow-up timing based on general business practices."
            }

        return APIResponse(
            success=True,
            data=suggestions
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/categorize", response_model=APIResponse)
async def categorize_contacts(contacts: List[Dict[str, Any]]):
    """
    Categorize multiple contacts by industry and type

    Useful for:
    - Bulk import categorization
    - Pipeline organization
    - Reporting
    """
    try:
        if not contacts:
            return APIResponse(success=True, data={"categorized": []})

        # Limit to prevent API abuse
        if len(contacts) > 50:
            raise HTTPException(
                status_code=400,
                detail="Maximum 50 contacts per request"
            )

        categorized = []

        for contact in contacts:
            try:
                result = claude_service.categorize_contact(contact)

                if not result.get("parse_error"):
                    categorized.append({
                        "contact": contact,
                        "industry": result.get("industry", "other"),
                        "contact_type": result.get("contact_type", "prospect"),
                        "company_size": result.get("company_size", "unknown"),
                        "priority": result.get("priority", "medium"),
                        "confidence": result.get("confidence", 0.5)
                    })
                else:
                    categorized.append({
                        "contact": contact,
                        "industry": "other",
                        "contact_type": "prospect",
                        "company_size": "unknown",
                        "priority": "medium",
                        "confidence": 0.3
                    })

            except Exception:
                categorized.append({
                    "contact": contact,
                    "industry": "other",
                    "contact_type": "prospect",
                    "company_size": "unknown",
                    "priority": "medium",
                    "confidence": 0.0,
                    "error": "Categorization failed"
                })

        return APIResponse(
            success=True,
            data={
                "total": len(contacts),
                "categorized": categorized
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _generate_suggestions(intent: Dict[str, Any], response: str) -> List[str]:
    """Generate suggested follow-up actions based on query intent"""
    suggestions = []

    query_type = intent.get("type", "general")

    if query_type == "contact_lookup":
        suggestions = [
            "View contact details",
            "Schedule follow-up",
            "Add notes",
            "Send message"
        ]
    elif query_type == "analytics":
        suggestions = [
            "Export report",
            "View by industry",
            "See follow-up due",
            "Filter contacts"
        ]
    elif query_type == "followup":
        suggestions = [
            "Mark as contacted",
            "Reschedule",
            "Add interaction note",
            "Skip this contact"
        ]
    elif query_type == "create":
        suggestions = [
            "Scan namecard",
            "Import spreadsheet",
            "Manual entry"
        ]
    else:
        suggestions = [
            "Search contacts",
            "View analytics",
            "Import data",
            "Settings"
        ]

    return suggestions[:4]


def _calculate_analytics(contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate analytics from contact list"""
    total = len(contacts)

    # Count by category
    by_category = {}
    by_industry = {}

    with_phone = 0
    with_email = 0

    for contact in contacts:
        # Category
        category = contact.get("category", "uncategorized")
        by_category[category] = by_category.get(category, 0) + 1

        # Industry
        industry = contact.get("industry", "unknown")
        if industry and industry != "unknown":
            by_industry[industry] = by_industry.get(industry, 0) + 1

        # Contact info
        if contact.get("phone"):
            with_phone += 1
        if contact.get("email"):
            with_email += 1

    return {
        "total": total,
        "by_category": by_category,
        "by_industry": by_industry,
        "with_phone": with_phone,
        "with_email": with_email,
        "phone_percentage": round(with_phone / max(1, total) * 100, 1),
        "email_percentage": round(with_email / max(1, total) * 100, 1)
    }
