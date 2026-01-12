"""
Claude AI service for ResultMarketing
Handles all Anthropic Claude API interactions
"""
import os
import time
import json
from typing import List, Dict, Any, Optional, Tuple
from anthropic import Anthropic
from config import settings


class ClaudeService:
    """Service class for Claude AI interactions"""

    def __init__(self):
        """Initialize Claude client"""
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.system_prompt = settings.system_prompt

    def chat_with_context(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]] = None,
        contact_context: str = None,
        max_tokens: int = 1024
    ) -> Tuple[str, int, int]:
        """
        Send a message to Claude with conversation history and context

        Args:
            user_message: The user's message
            conversation_history: Previous messages in the conversation
            contact_context: Contact data context to include
            max_tokens: Maximum tokens in response

        Returns:
            Tuple of (response_text, input_tokens, output_tokens)
        """
        messages = []

        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

        # Build user message with context
        full_message = user_message
        if contact_context:
            full_message = f"""Context about user's contacts:
{contact_context}

User's question: {user_message}

Please answer based on the context provided. If the information isn't in the context, let the user know."""

        messages.append({
            "role": "user",
            "content": full_message
        })

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=self.system_prompt,
                messages=messages
            )

            response_text = response.content[0].text
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            return response_text, input_tokens, output_tokens

        except Exception as e:
            raise Exception(f"Claude API error: {str(e)}")

    def analyze_spreadsheet(
        self,
        columns: List[str],
        sample_data: List[Dict[str, Any]],
        row_count: int
    ) -> Dict[str, Any]:
        """
        Analyze spreadsheet structure and suggest column mappings

        Args:
            columns: List of column names
            sample_data: Sample rows from the spreadsheet
            row_count: Total number of rows

        Returns:
            Analysis results with column mappings and recommendations
        """
        prompt = f"""Analyze this spreadsheet structure for a CRM contact import:

Column names: {json.dumps(columns)}

Sample data (first 5 rows):
{json.dumps(sample_data[:5], indent=2, default=str)}

Total rows: {row_count}

Please analyze and provide:
1. Map each column to a standard field (name, phone, email, company, title, industry, address, notes, source, status) or mark as "unknown"
2. Confidence score (0-1) for each mapping
3. Data quality observations
4. Suggested cleaning actions

Respond in JSON format:
{{
    "column_mappings": {{
        "original_column_name": {{
            "mapped_to": "standard_field_or_unknown",
            "confidence": 0.0-1.0,
            "reason": "why this mapping"
        }}
    }},
    "data_quality": {{
        "overall_score": 0-100,
        "issues": ["list of issues found"],
        "recommendations": ["suggested actions"]
    }},
    "contact_count_estimate": number,
    "duplicate_risk": "low/medium/high"
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system="You are a data analysis expert. Analyze spreadsheet structures and provide accurate column mappings. Always respond with valid JSON only.",
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # Try to parse JSON response
            try:
                # Find JSON in response (in case there's extra text)
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            # Return raw response if JSON parsing fails
            return {
                "raw_analysis": response_text,
                "parse_error": True
            }

        except Exception as e:
            raise Exception(f"Spreadsheet analysis error: {str(e)}")

    def extract_contact_info(self, text: str) -> Dict[str, Any]:
        """
        Extract contact information from text (OCR result)

        Args:
            text: Raw text from OCR or user input

        Returns:
            Extracted contact fields with confidence scores
        """
        prompt = f"""Extract contact information from this text (likely from a business card or namecard):

Text:
{text}

Extract the following fields if present:
- name: Full name of the person
- title: Job title/position
- company: Company/organization name
- phone: Phone number(s) - format as Malaysian numbers if applicable
- email: Email address(es)
- address: Office/business address
- website: Website URL if present

For Malaysian numbers:
- Mobile typically starts with +60 10/11/12/13/14/16/17/18/19
- Landline typically starts with +60 3/4/5/6/7/8/9

Respond in JSON format:
{{
    "name": {{"value": "extracted name", "confidence": 0.0-1.0}},
    "title": {{"value": "extracted title", "confidence": 0.0-1.0}},
    "company": {{"value": "extracted company", "confidence": 0.0-1.0}},
    "phone": {{"value": "extracted phone", "confidence": 0.0-1.0}},
    "email": {{"value": "extracted email", "confidence": 0.0-1.0}},
    "address": {{"value": "extracted address", "confidence": 0.0-1.0}},
    "detected_language": "en/ms/zh",
    "overall_confidence": 0.0-1.0
}}

Use null for fields that cannot be found. Confidence should reflect how certain you are about each extraction."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system="You are an expert at extracting structured information from business cards. Always respond with valid JSON only.",
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # Parse JSON response
            try:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            return {
                "raw_response": response_text,
                "parse_error": True
            }

        except Exception as e:
            raise Exception(f"Contact extraction error: {str(e)}")

    def generate_follow_up_suggestions(
        self,
        contact: Dict[str, Any],
        interaction_history: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate follow-up timing and message suggestions

        Args:
            contact: Contact information
            interaction_history: Previous interactions with this contact

        Returns:
            Follow-up suggestions
        """
        history_text = ""
        if interaction_history:
            history_text = f"\n\nPrevious interactions:\n{json.dumps(interaction_history, indent=2, default=str)}"

        prompt = f"""Based on this Malaysian business contact, suggest follow-up timing and approach:

Contact:
{json.dumps(contact, indent=2, default=str)}
{history_text}

Consider:
- Malaysian business culture (relationship-building is important)
- Industry-specific cadences
- Best times to reach out (business hours GMT+8)
- Upcoming holidays that might affect timing

Provide suggestions in JSON format:
{{
    "recommended_follow_up_days": number,
    "best_contact_time": "morning/afternoon/evening",
    "suggested_approach": "call/email/whatsapp",
    "message_template": "suggested message text",
    "reasoning": "why these recommendations",
    "avoid_dates": ["any dates to avoid like holidays"]
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            try:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            return {
                "raw_response": response_text,
                "parse_error": True
            }

        except Exception as e:
            raise Exception(f"Follow-up suggestion error: {str(e)}")

    def categorize_contact(self, contact: Dict[str, Any]) -> Dict[str, Any]:
        """
        Categorize a contact by industry and type

        Args:
            contact: Contact information

        Returns:
            Categorization results
        """
        prompt = f"""Categorize this Malaysian business contact:

{json.dumps(contact, indent=2, default=str)}

Determine:
1. Industry category (technology, finance, healthcare, retail, manufacturing, services, real_estate, education, government, other)
2. Contact type (prospect, client, partner, vendor, other)
3. Company size estimate if possible (startup, sme, enterprise, unknown)
4. Priority level (high, medium, low) based on potential

Respond in JSON:
{{
    "industry": "category",
    "contact_type": "type",
    "company_size": "size",
    "priority": "level",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                system="You are a business analyst expert in Malaysian markets. Categorize contacts accurately. Respond with JSON only.",
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            try:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            return {
                "industry": "other",
                "contact_type": "prospect",
                "company_size": "unknown",
                "priority": "medium",
                "confidence": 0.5
            }

        except Exception as e:
            raise Exception(f"Contact categorization error: {str(e)}")


    def extract_voice_note_info(
        self,
        transcription: str,
        user_contacts: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Extract structured information from voice note transcription

        Args:
            transcription: Transcribed text from voice note
            user_contacts: List of user's existing contacts for name matching

        Returns:
            Extracted information including contact info, action items, etc.
        """
        contacts_context = ""
        if user_contacts:
            contact_names = [c.get('name', '') for c in user_contacts[:50] if c.get('name')]
            if contact_names:
                contacts_context = f"\n\nUser's existing contacts (for name matching): {', '.join(contact_names)}"

        prompt = f"""Analyze this voice note transcription and extract structured information:

Transcription:
{transcription}
{contacts_context}

Extract the following:
1. Any new contact information mentioned (name, phone, email, company)
2. Action items or tasks mentioned
3. Names of existing contacts mentioned (match against user's contacts if provided)
4. Any follow-up dates or deadlines mentioned
5. A brief summary of the voice note

Consider Malaysian context:
- Phone numbers may start with 01x or +601x
- Company names might include "Sdn Bhd", "Berhad", etc.
- Dates might be in various formats

Respond in JSON format:
{{
    "contact_info": {{
        "name": "extracted name or null",
        "phone": "extracted phone or null",
        "email": "extracted email or null",
        "company": "extracted company or null"
    }},
    "action_items": ["list of action items"],
    "mentioned_contacts": ["names matching user's contacts"],
    "follow_up_date": "extracted date or null",
    "summary": "brief summary of voice note"
}}

If no information is found for a field, use null or empty array."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system="You are an assistant that extracts structured information from voice note transcriptions. Always respond with valid JSON only.",
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            try:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            return {
                "contact_info": None,
                "action_items": [],
                "mentioned_contacts": [],
                "follow_up_date": None,
                "summary": transcription[:200] + "..." if len(transcription) > 200 else transcription
            }

        except Exception as e:
            raise Exception(f"Voice note extraction error: {str(e)}")


# Create singleton instance
claude_service = ClaudeService()


# Helper function for whisper_service.py
async def extract_voice_note_info(
    transcription: str,
    user_contacts: List[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Async wrapper for voice note extraction"""
    return claude_service.extract_voice_note_info(transcription, user_contacts)
