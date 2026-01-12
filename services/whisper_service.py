"""
Whisper Voice Processing Service
ResultMarketing CRM - OpenAI Whisper Integration
"""

import os
import io
import time
from typing import Optional, Dict, Any, List
from openai import OpenAI
from pydantic import BaseModel

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Supported audio formats
SUPPORTED_FORMATS = [
    "mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm",
    "flac", "ogg", "opus"
]

# Maximum file size (25 MB for Whisper)
MAX_FILE_SIZE = 25 * 1024 * 1024


class TranscriptionResult(BaseModel):
    """Transcription result model"""
    text: str
    language: Optional[str] = None
    duration: Optional[float] = None
    confidence: Optional[float] = None
    words: Optional[List[Dict[str, Any]]] = None
    processing_time: float


class VoiceNoteExtraction(BaseModel):
    """Extracted information from voice note"""
    transcription: str
    contact_info: Optional[Dict[str, Any]] = None
    action_items: List[str] = []
    mentioned_contacts: List[str] = []
    follow_up_date: Optional[str] = None
    summary: Optional[str] = None
    language: str = "en"


async def transcribe_audio(
    audio_content: bytes,
    filename: str = "audio.mp3",
    language: Optional[str] = None,
    response_format: str = "verbose_json"
) -> TranscriptionResult:
    """
    Transcribe audio file using OpenAI Whisper

    Args:
        audio_content: Raw audio file bytes
        filename: Original filename (for format detection)
        language: Optional language hint (ISO 639-1 code)
        response_format: Output format (json, text, srt, verbose_json, vtt)

    Returns:
        TranscriptionResult with transcription text and metadata
    """
    start_time = time.time()

    # Validate file size
    if len(audio_content) > MAX_FILE_SIZE:
        raise ValueError(f"File too large. Maximum size is {MAX_FILE_SIZE / (1024*1024):.0f} MB")

    # Get file extension
    ext = filename.split(".")[-1].lower() if "." in filename else "mp3"
    if ext not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: {ext}. Supported: {', '.join(SUPPORTED_FORMATS)}")

    # Create file-like object
    audio_file = io.BytesIO(audio_content)
    audio_file.name = filename

    # Prepare transcription parameters
    params = {
        "model": "whisper-1",
        "file": audio_file,
        "response_format": response_format,
    }

    if language:
        params["language"] = language

    # Call Whisper API
    response = client.audio.transcriptions.create(**params)

    processing_time = time.time() - start_time

    # Parse response based on format
    if response_format == "verbose_json":
        return TranscriptionResult(
            text=response.text,
            language=response.language,
            duration=response.duration,
            words=getattr(response, 'words', None),
            processing_time=processing_time
        )
    elif response_format == "json":
        return TranscriptionResult(
            text=response.text,
            processing_time=processing_time
        )
    else:
        # Text, SRT, VTT formats
        return TranscriptionResult(
            text=response if isinstance(response, str) else str(response),
            processing_time=processing_time
        )


async def transcribe_and_translate(
    audio_content: bytes,
    filename: str = "audio.mp3",
    target_language: str = "en"
) -> TranscriptionResult:
    """
    Transcribe and translate audio to English

    Args:
        audio_content: Raw audio file bytes
        filename: Original filename
        target_language: Target language (currently only English supported)

    Returns:
        TranscriptionResult with translated text
    """
    start_time = time.time()

    if len(audio_content) > MAX_FILE_SIZE:
        raise ValueError(f"File too large. Maximum size is {MAX_FILE_SIZE / (1024*1024):.0f} MB")

    audio_file = io.BytesIO(audio_content)
    audio_file.name = filename

    # Use translation endpoint
    response = client.audio.translations.create(
        model="whisper-1",
        file=audio_file,
        response_format="verbose_json"
    )

    processing_time = time.time() - start_time

    return TranscriptionResult(
        text=response.text,
        language="en",  # Translation is always to English
        duration=response.duration,
        processing_time=processing_time
    )


async def extract_info_from_voice_note(
    audio_content: bytes,
    filename: str = "audio.mp3",
    user_contacts: Optional[List[Dict[str, str]]] = None
) -> VoiceNoteExtraction:
    """
    Transcribe voice note and extract structured information

    Args:
        audio_content: Raw audio file bytes
        filename: Original filename
        user_contacts: List of user's existing contacts for name matching

    Returns:
        VoiceNoteExtraction with transcription and extracted information
    """
    # First, transcribe the audio
    transcription = await transcribe_audio(
        audio_content,
        filename,
        response_format="verbose_json"
    )

    # If transcription is empty, return early
    if not transcription.text.strip():
        return VoiceNoteExtraction(
            transcription="",
            language=transcription.language or "en"
        )

    # Use Claude to extract information from transcription
    from services.claude_service import extract_voice_note_info

    extraction = await extract_voice_note_info(
        transcription.text,
        user_contacts or []
    )

    return VoiceNoteExtraction(
        transcription=transcription.text,
        contact_info=extraction.get("contact_info"),
        action_items=extraction.get("action_items", []),
        mentioned_contacts=extraction.get("mentioned_contacts", []),
        follow_up_date=extraction.get("follow_up_date"),
        summary=extraction.get("summary"),
        language=transcription.language or "en"
    )


async def process_voice_memo(
    audio_content: bytes,
    filename: str = "audio.mp3",
    context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a voice memo for the AI chat interface

    Args:
        audio_content: Raw audio file bytes
        filename: Original filename
        context: Optional context about what the voice memo is for

    Returns:
        Dict with transcription and processed query for chat
    """
    # Transcribe
    transcription = await transcribe_audio(
        audio_content,
        filename,
        response_format="verbose_json"
    )

    return {
        "success": True,
        "transcription": transcription.text,
        "language": transcription.language,
        "duration": transcription.duration,
        "processing_time": transcription.processing_time,
        "query": transcription.text,  # Use transcription as chat query
        "context": context
    }


def validate_audio_file(
    content: bytes,
    filename: str
) -> Dict[str, Any]:
    """
    Validate audio file before processing

    Args:
        content: File content bytes
        filename: Original filename

    Returns:
        Dict with validation status and details
    """
    # Check file size
    size = len(content)
    if size > MAX_FILE_SIZE:
        return {
            "valid": False,
            "error": f"File too large ({size / (1024*1024):.1f} MB). Maximum is {MAX_FILE_SIZE / (1024*1024):.0f} MB"
        }

    if size < 100:  # Minimum reasonable audio file size
        return {
            "valid": False,
            "error": "File too small to be a valid audio file"
        }

    # Check format
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_FORMATS:
        return {
            "valid": False,
            "error": f"Unsupported format: {ext}. Supported: {', '.join(SUPPORTED_FORMATS)}"
        }

    return {
        "valid": True,
        "size": size,
        "format": ext,
        "size_mb": round(size / (1024 * 1024), 2)
    }


def get_supported_formats() -> List[str]:
    """Get list of supported audio formats"""
    return SUPPORTED_FORMATS.copy()


def get_max_file_size() -> int:
    """Get maximum file size in bytes"""
    return MAX_FILE_SIZE
