"""
Google Vision OCR service for namecard processing
"""
import os
import base64
import re
import time
from typing import Dict, Any, Optional, List, Tuple
from google.cloud import vision
from google.cloud.vision_v1 import types
from config import settings, OCR_CONFIDENCE_THRESHOLDS
from utils.phone_formatter import extract_phone_numbers, format_malaysian_phone


class VisionService:
    """Service class for Google Cloud Vision OCR"""

    def __init__(self):
        """Initialize Vision client"""
        if settings.google_credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_credentials_path

        try:
            self.client = vision.ImageAnnotatorClient()
            self.initialized = True
        except Exception as e:
            print(f"Warning: Google Vision client not initialized: {e}")
            self.client = None
            self.initialized = False

    def extract_text_from_image(
        self,
        image_content: bytes = None,
        image_base64: str = None,
        image_uri: str = None
    ) -> Dict[str, Any]:
        """
        Extract text from an image using Google Vision OCR

        Args:
            image_content: Raw image bytes
            image_base64: Base64 encoded image
            image_uri: URI of image (GCS or web URL)

        Returns:
            OCR results with text, confidence, and language
        """
        start_time = time.time()

        if not self.initialized:
            return {
                "success": False,
                "error": "Google Vision client not initialized",
                "text": "",
                "confidence": 0.0
            }

        try:
            # Build image object
            if image_content:
                image = types.Image(content=image_content)
            elif image_base64:
                # Remove data URL prefix if present
                if "," in image_base64:
                    image_base64 = image_base64.split(",")[1]
                image_bytes = base64.b64decode(image_base64)
                image = types.Image(content=image_bytes)
            elif image_uri:
                image = types.Image()
                image.source.image_uri = image_uri
            else:
                return {
                    "success": False,
                    "error": "No image provided",
                    "text": "",
                    "confidence": 0.0
                }

            # Perform text detection
            response = self.client.text_detection(image=image)

            if response.error.message:
                return {
                    "success": False,
                    "error": response.error.message,
                    "text": "",
                    "confidence": 0.0
                }

            # Extract text and annotations
            texts = response.text_annotations

            if not texts:
                return {
                    "success": True,
                    "text": "",
                    "confidence": 0.0,
                    "language": "unknown",
                    "processing_time_ms": int((time.time() - start_time) * 1000)
                }

            # First annotation contains full text
            full_text = texts[0].description

            # Get language detection
            detected_language = "en"
            if response.full_text_annotation.pages:
                page = response.full_text_annotation.pages[0]
                if page.property and page.property.detected_languages:
                    detected_language = page.property.detected_languages[0].language_code

            # Calculate average confidence from word-level annotations
            confidences = []
            if response.full_text_annotation.pages:
                for page in response.full_text_annotation.pages:
                    for block in page.blocks:
                        confidences.append(block.confidence)

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.8

            return {
                "success": True,
                "text": full_text,
                "confidence": avg_confidence,
                "language": detected_language,
                "word_count": len(texts) - 1,  # Exclude full text annotation
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "confidence": 0.0,
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }

    def parse_namecard_text(self, ocr_text: str) -> Dict[str, Any]:
        """
        Parse OCR text to extract namecard fields

        Args:
            ocr_text: Raw text from OCR

        Returns:
            Parsed namecard fields with confidence scores
        """
        result = {
            "name": None,
            "title": None,
            "company": None,
            "phone": None,
            "email": None,
            "address": None,
            "website": None,
            "confidence_scores": {},
            "overall_confidence": 0.0
        }

        if not ocr_text:
            return result

        lines = [line.strip() for line in ocr_text.split("\n") if line.strip()]

        # Extract email
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        email_matches = re.findall(email_pattern, ocr_text)
        if email_matches:
            result["email"] = email_matches[0].lower()
            result["confidence_scores"]["email"] = 0.95

        # Extract phone numbers
        phones = extract_phone_numbers(ocr_text)
        if phones:
            formatted = format_malaysian_phone(phones[0])
            result["phone"] = formatted or phones[0]
            result["confidence_scores"]["phone"] = 0.9 if formatted else 0.7

        # Extract website
        website_pattern = r"(?:www\.)?[a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?"
        website_matches = re.findall(website_pattern, ocr_text.lower())
        for match in website_matches:
            if not "@" in match and match not in ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]:
                result["website"] = match if match.startswith("www.") else f"www.{match}"
                result["confidence_scores"]["website"] = 0.85
                break

        # Heuristics for name, title, company (more complex logic)
        remaining_lines = []
        for line in lines:
            # Skip lines that are clearly phone/email/website
            if "@" in line:
                continue
            if re.match(r"^[\d\s\-\+\(\)]+$", line):
                continue
            if "www." in line.lower() or ".com" in line.lower():
                continue
            remaining_lines.append(line)

        # Common title keywords
        title_keywords = [
            "director", "manager", "ceo", "cto", "cfo", "executive", "officer",
            "president", "vp", "vice president", "head", "lead", "senior",
            "engineer", "developer", "analyst", "consultant", "specialist",
            "associate", "assistant", "coordinator", "supervisor", "admin",
            "sales", "marketing", "hr", "human resource", "finance",
            "pengarah", "pengurus", "eksekutif"  # Malay titles
        ]

        # Company keywords
        company_keywords = [
            "sdn bhd", "sdn. bhd.", "berhad", "bhd", "plt", "llp",
            "pte ltd", "pte. ltd.", "inc", "corp", "corporation",
            "enterprise", "enterprises", "group", "holdings",
            "industries", "solutions", "services", "consulting",
            "teknologi", "syarikat"  # Malay
        ]

        # Identify company line
        for i, line in enumerate(remaining_lines):
            line_lower = line.lower()
            if any(kw in line_lower for kw in company_keywords):
                result["company"] = line
                result["confidence_scores"]["company"] = 0.9
                remaining_lines[i] = None
                break

        # Identify title line
        remaining_lines = [l for l in remaining_lines if l is not None]
        for i, line in enumerate(remaining_lines):
            line_lower = line.lower()
            if any(kw in line_lower for kw in title_keywords):
                result["title"] = line
                result["confidence_scores"]["title"] = 0.85
                remaining_lines[i] = None
                break

        # First remaining line is likely name
        remaining_lines = [l for l in remaining_lines if l is not None]
        if remaining_lines:
            # Name heuristics: typically 2-4 words, may have titles like Dr., Dato', etc.
            potential_name = remaining_lines[0]
            # Check if it's a reasonable name (not too long, not all caps company name)
            word_count = len(potential_name.split())
            if word_count <= 5 and not any(kw in potential_name.lower() for kw in company_keywords):
                result["name"] = potential_name
                result["confidence_scores"]["name"] = 0.75

        # Address is typically multi-line with numbers and location keywords
        address_keywords = ["jalan", "jln", "no.", "lot", "level", "floor", "tower",
                          "kuala lumpur", "kl", "selangor", "penang", "johor", "malaysia",
                          "street", "road", "avenue", "building"]

        address_parts = []
        for line in lines:
            line_lower = line.lower()
            if any(kw in line_lower for kw in address_keywords):
                address_parts.append(line)
            # Lines with postal codes
            elif re.search(r"\d{5}", line):
                address_parts.append(line)

        if address_parts:
            result["address"] = ", ".join(address_parts)
            result["confidence_scores"]["address"] = 0.7

        # Calculate overall confidence
        scores = list(result["confidence_scores"].values())
        result["overall_confidence"] = sum(scores) / len(scores) if scores else 0.0

        # Determine confidence level
        if result["overall_confidence"] >= OCR_CONFIDENCE_THRESHOLDS["high"]:
            result["confidence_level"] = "high"
        elif result["overall_confidence"] >= OCR_CONFIDENCE_THRESHOLDS["medium"]:
            result["confidence_level"] = "medium"
        else:
            result["confidence_level"] = "low"

        return result

    def process_namecard(
        self,
        image_content: bytes = None,
        image_base64: str = None,
        image_uri: str = None
    ) -> Dict[str, Any]:
        """
        Complete namecard processing pipeline

        Args:
            image_content: Raw image bytes
            image_base64: Base64 encoded image
            image_uri: URI of image

        Returns:
            Complete namecard processing result
        """
        start_time = time.time()

        # Step 1: Extract text
        ocr_result = self.extract_text_from_image(
            image_content=image_content,
            image_base64=image_base64,
            image_uri=image_uri
        )

        if not ocr_result["success"]:
            return {
                "success": False,
                "error": ocr_result.get("error", "OCR failed"),
                "contact": None,
                "raw_text": "",
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }

        # Step 2: Parse namecard text
        parsed = self.parse_namecard_text(ocr_result["text"])

        return {
            "success": True,
            "contact": {
                "name": parsed["name"],
                "title": parsed["title"],
                "company": parsed["company"],
                "phone": parsed["phone"],
                "email": parsed["email"],
                "address": parsed["address"],
                "website": parsed["website"]
            },
            "confidence_scores": parsed["confidence_scores"],
            "overall_confidence": parsed["overall_confidence"],
            "confidence_level": parsed.get("confidence_level", "low"),
            "raw_text": ocr_result["text"],
            "detected_language": ocr_result.get("language", "en"),
            "processing_time_ms": int((time.time() - start_time) * 1000)
        }


# Create singleton instance
vision_service = VisionService()
