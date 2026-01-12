"""
Voice Processing Router
ResultMarketing CRM - Whisper Voice Endpoints
"""

import os
import time
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from pydantic import BaseModel

from services.whisper_service import (
    transcribe_audio,
    transcribe_and_translate,
    extract_info_from_voice_note,
    process_voice_memo,
    validate_audio_file,
    get_supported_formats,
    get_max_file_size
)

router = APIRouter(prefix="/api/voice", tags=["voice"])


# ===========================================
# RESPONSE MODELS
# ===========================================

class TranscriptionResponse(BaseModel):
    success: bool
    text: str
    language: Optional[str] = None
    duration: Optional[float] = None
    processing_time: float
    error: Optional[str] = None


class VoiceNoteResponse(BaseModel):
    success: bool
    transcription: str
    contact_info: Optional[dict] = None
    action_items: List[str] = []
    mentioned_contacts: List[str] = []
    follow_up_date: Optional[str] = None
    summary: Optional[str] = None
    language: str = "en"
    error: Optional[str] = None


class VoiceChatResponse(BaseModel):
    success: bool
    transcription: str
    language: Optional[str] = None
    duration: Optional[float] = None
    processing_time: float
    query: str
    error: Optional[str] = None


class ValidationResponse(BaseModel):
    valid: bool
    size: Optional[int] = None
    size_mb: Optional[float] = None
    format: Optional[str] = None
    error: Optional[str] = None


class FormatsResponse(BaseModel):
    formats: List[str]
    max_file_size_mb: int


# ===========================================
# ENDPOINTS
# ===========================================

@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_voice(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    language: Optional[str] = Form(None, description="Language hint (ISO 639-1 code, e.g., 'en', 'ms', 'zh')")
):
    """
    Transcribe audio file to text using OpenAI Whisper

    Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm, flac, ogg, opus
    Maximum file size: 25 MB
    """
    try:
        # Read file content
        content = await file.read()

        # Validate file
        validation = validate_audio_file(content, file.filename or "audio.mp3")
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail=validation["error"])

        # Transcribe
        result = await transcribe_audio(
            content,
            file.filename or "audio.mp3",
            language=language
        )

        return TranscriptionResponse(
            success=True,
            text=result.text,
            language=result.language,
            duration=result.duration,
            processing_time=result.processing_time
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@router.post("/translate", response_model=TranscriptionResponse)
async def translate_voice(
    file: UploadFile = File(..., description="Audio file to translate to English")
):
    """
    Transcribe and translate audio file to English

    Useful for voice notes in Bahasa Malaysia, Chinese, or other languages.
    The output will always be in English.
    """
    try:
        content = await file.read()

        validation = validate_audio_file(content, file.filename or "audio.mp3")
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail=validation["error"])

        result = await transcribe_and_translate(
            content,
            file.filename or "audio.mp3"
        )

        return TranscriptionResponse(
            success=True,
            text=result.text,
            language="en",
            duration=result.duration,
            processing_time=result.processing_time
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")


@router.post("/extract", response_model=VoiceNoteResponse)
async def extract_from_voice(
    file: UploadFile = File(..., description="Voice note to process"),
    contacts_json: Optional[str] = Form(None, description="JSON array of existing contacts for name matching")
):
    """
    Transcribe voice note and extract structured information

    Extracts:
    - Contact information mentioned
    - Action items and tasks
    - Names of mentioned contacts
    - Follow-up dates
    - Summary of the voice note
    """
    try:
        import json

        content = await file.read()

        validation = validate_audio_file(content, file.filename or "audio.mp3")
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail=validation["error"])

        # Parse contacts if provided
        user_contacts = None
        if contacts_json:
            try:
                user_contacts = json.loads(contacts_json)
            except json.JSONDecodeError:
                pass  # Ignore invalid JSON

        result = await extract_info_from_voice_note(
            content,
            file.filename or "audio.mp3",
            user_contacts
        )

        return VoiceNoteResponse(
            success=True,
            transcription=result.transcription,
            contact_info=result.contact_info,
            action_items=result.action_items,
            mentioned_contacts=result.mentioned_contacts,
            follow_up_date=result.follow_up_date,
            summary=result.summary,
            language=result.language
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/chat", response_model=VoiceChatResponse)
async def voice_to_chat(
    file: UploadFile = File(..., description="Voice message for AI chat"),
    context: Optional[str] = Form(None, description="Optional context about the voice message")
):
    """
    Process voice message for the AI chat interface

    Converts voice to text and prepares it as a chat query.
    Use this when the user wants to speak their question instead of typing.
    """
    try:
        content = await file.read()

        validation = validate_audio_file(content, file.filename or "audio.mp3")
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail=validation["error"])

        result = await process_voice_memo(
            content,
            file.filename or "audio.mp3",
            context
        )

        return VoiceChatResponse(
            success=True,
            transcription=result["transcription"],
            language=result.get("language"),
            duration=result.get("duration"),
            processing_time=result["processing_time"],
            query=result["query"]
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/validate", response_model=ValidationResponse)
async def validate_voice_file(
    file: UploadFile = File(..., description="Audio file to validate")
):
    """
    Validate audio file before processing

    Checks file size, format, and basic validity.
    Use this for client-side validation before uploading large files.
    """
    try:
        content = await file.read()
        result = validate_audio_file(content, file.filename or "audio.mp3")

        return ValidationResponse(
            valid=result["valid"],
            size=result.get("size"),
            size_mb=result.get("size_mb"),
            format=result.get("format"),
            error=result.get("error")
        )

    except Exception as e:
        return ValidationResponse(
            valid=False,
            error=str(e)
        )


@router.get("/formats", response_model=FormatsResponse)
async def get_voice_formats():
    """
    Get supported audio formats and limits

    Returns list of supported formats and maximum file size.
    """
    return FormatsResponse(
        formats=get_supported_formats(),
        max_file_size_mb=get_max_file_size() // (1024 * 1024)
    )


@router.post("/batch-transcribe")
async def batch_transcribe(
    files: List[UploadFile] = File(..., description="Multiple audio files (max 5)"),
    language: Optional[str] = Form(None, description="Language hint")
):
    """
    Transcribe multiple audio files in batch

    Maximum 5 files per request.
    """
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 files per batch")

    results = []

    for file in files:
        try:
            content = await file.read()

            validation = validate_audio_file(content, file.filename or "audio.mp3")
            if not validation["valid"]:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": validation["error"]
                })
                continue

            result = await transcribe_audio(
                content,
                file.filename or "audio.mp3",
                language=language
            )

            results.append({
                "filename": file.filename,
                "success": True,
                "text": result.text,
                "language": result.language,
                "duration": result.duration,
                "processing_time": result.processing_time
            })

        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })

    return {
        "success": True,
        "total": len(files),
        "successful": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "results": results
    }
