"""
Namecard/business card OCR processing endpoints
"""
import time
import base64
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from models.schemas import (
    NamecardScanRequest,
    NamecardResult,
    ContactDataWithConfidence,
    ProcessingStatus,
    ConfidenceLevel,
    APIResponse
)
from services.vision_service import vision_service
from services.claude_service import claude_service


router = APIRouter(prefix="/api/namecard", tags=["Namecard"])


@router.post("/scan", response_model=APIResponse)
async def scan_namecard(
    file: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = Form(None),
    image_url: Optional[str] = Form(None),
    use_ai_extraction: bool = Form(True)
):
    """
    Process a namecard/business card image and extract contact information

    Accepts image via:
    - File upload
    - Base64 encoded string
    - Image URL

    Returns extracted contact fields with confidence scores
    """
    start_time = time.time()

    try:
        # Validate input - need at least one image source
        if not file and not image_base64 and not image_url:
            raise HTTPException(
                status_code=400,
                detail="No image provided. Upload a file, provide base64, or provide URL."
            )

        # Process based on input type
        image_content = None
        image_b64 = None

        if file:
            # Validate file type
            content_type = file.content_type or ""
            if not content_type.startswith("image/"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type: {content_type}. Please upload an image."
                )

            image_content = await file.read()

            if len(image_content) == 0:
                raise HTTPException(status_code=400, detail="Empty file uploaded")

            # Check file size (max 10MB)
            if len(image_content) > 10 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail="File too large. Maximum size is 10MB."
                )

        elif image_base64:
            image_b64 = image_base64

        # Process with Vision service
        result = vision_service.process_namecard(
            image_content=image_content,
            image_base64=image_b64,
            image_uri=image_url
        )

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"OCR processing failed: {result.get('error', 'Unknown error')}"
            )

        # Enhance extraction with Claude if requested and OCR confidence is low
        contact_data = result["contact"]
        confidence_scores = result["confidence_scores"]
        overall_confidence = result["overall_confidence"]

        if use_ai_extraction and result["raw_text"]:
            try:
                ai_result = claude_service.extract_contact_info(result["raw_text"])

                if not ai_result.get("parse_error"):
                    # Merge AI results with OCR results, preferring higher confidence
                    for field in ["name", "title", "company", "phone", "email", "address"]:
                        ai_field = ai_result.get(field, {})
                        if isinstance(ai_field, dict):
                            ai_value = ai_field.get("value")
                            ai_confidence = ai_field.get("confidence", 0)

                            ocr_confidence = confidence_scores.get(field, 0)

                            # Use AI result if it has higher confidence or OCR is missing
                            if ai_value and (ai_confidence > ocr_confidence or not contact_data.get(field)):
                                contact_data[field] = ai_value
                                confidence_scores[field] = max(ai_confidence, ocr_confidence)

                    # Update overall confidence
                    if ai_result.get("overall_confidence"):
                        overall_confidence = max(
                            overall_confidence,
                            ai_result["overall_confidence"]
                        )

            except Exception as e:
                # AI enhancement is optional, continue with OCR results
                pass

        # Determine confidence level
        if overall_confidence >= 0.9:
            confidence_level = ConfidenceLevel.HIGH
        elif overall_confidence >= 0.7:
            confidence_level = ConfidenceLevel.MEDIUM
        else:
            confidence_level = ConfidenceLevel.LOW

        # Build response
        contact_with_confidence = ContactDataWithConfidence(
            name=contact_data.get("name"),
            phone=contact_data.get("phone"),
            email=contact_data.get("email"),
            company=contact_data.get("company"),
            title=contact_data.get("title"),
            address=contact_data.get("address"),
            confidence_scores=confidence_scores,
            overall_confidence=overall_confidence,
            confidence_level=confidence_level
        )

        namecard_result = NamecardResult(
            contact=contact_with_confidence,
            raw_text=result["raw_text"],
            detected_language=result.get("detected_language", "en"),
            processing_time_ms=int((time.time() - start_time) * 1000),
            status=ProcessingStatus.COMPLETED,
            message="Namecard processed successfully"
        )

        return APIResponse(
            success=True,
            data=namecard_result.model_dump()
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan-batch", response_model=APIResponse)
async def scan_namecard_batch(
    files: list[UploadFile] = File(...)
):
    """
    Process multiple namecard images in batch

    Returns results for each image with success/failure status
    """
    start_time = time.time()

    if len(files) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 images per batch"
        )

    results = []

    for i, file in enumerate(files):
        try:
            content_type = file.content_type or ""
            if not content_type.startswith("image/"):
                results.append({
                    "index": i,
                    "filename": file.filename,
                    "success": False,
                    "error": f"Invalid file type: {content_type}"
                })
                continue

            image_content = await file.read()

            if len(image_content) == 0:
                results.append({
                    "index": i,
                    "filename": file.filename,
                    "success": False,
                    "error": "Empty file"
                })
                continue

            # Process image
            result = vision_service.process_namecard(image_content=image_content)

            if result["success"]:
                # Try AI enhancement
                contact_data = result["contact"]
                if result["raw_text"]:
                    try:
                        ai_result = claude_service.extract_contact_info(result["raw_text"])
                        if not ai_result.get("parse_error"):
                            for field in ["name", "title", "company", "phone", "email"]:
                                ai_field = ai_result.get(field, {})
                                if isinstance(ai_field, dict) and ai_field.get("value"):
                                    if not contact_data.get(field):
                                        contact_data[field] = ai_field["value"]
                    except Exception:
                        pass

                results.append({
                    "index": i,
                    "filename": file.filename,
                    "success": True,
                    "contact": contact_data,
                    "confidence": result["overall_confidence"],
                    "raw_text": result["raw_text"]
                })
            else:
                results.append({
                    "index": i,
                    "filename": file.filename,
                    "success": False,
                    "error": result.get("error", "Processing failed")
                })

        except Exception as e:
            results.append({
                "index": i,
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })

    successful = sum(1 for r in results if r["success"])

    return APIResponse(
        success=True,
        data={
            "total": len(files),
            "successful": successful,
            "failed": len(files) - successful,
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "results": results
        }
    )


@router.post("/extract-text", response_model=APIResponse)
async def extract_text_only(
    file: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = Form(None),
    image_url: Optional[str] = Form(None)
):
    """
    Extract raw text from image without parsing into contact fields

    Useful for debugging or custom parsing
    """
    try:
        if not file and not image_base64 and not image_url:
            raise HTTPException(
                status_code=400,
                detail="No image provided"
            )

        image_content = None
        image_b64 = None

        if file:
            image_content = await file.read()
        elif image_base64:
            image_b64 = image_base64

        result = vision_service.extract_text_from_image(
            image_content=image_content,
            image_base64=image_b64,
            image_uri=image_url
        )

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"OCR failed: {result.get('error')}"
            )

        return APIResponse(
            success=True,
            data={
                "text": result["text"],
                "confidence": result["confidence"],
                "language": result.get("language", "unknown"),
                "word_count": result.get("word_count", 0),
                "processing_time_ms": result.get("processing_time_ms", 0)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
