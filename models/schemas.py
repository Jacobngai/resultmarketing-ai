"""
Pydantic models for ResultMarketing AI Microservice
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from enum import Enum
from datetime import datetime


# ============ Enums ============

class ProcessingStatus(str, Enum):
    """Status of processing operations"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfidenceLevel(str, Enum):
    """Confidence level for OCR and AI results"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ContactCategory(str, Enum):
    """Contact category types"""
    PROSPECT = "prospect"
    CLIENT = "client"
    PARTNER = "partner"
    VENDOR = "vendor"
    OTHER = "other"


# ============ Contact Data Models ============

class ContactData(BaseModel):
    """Contact information model"""
    name: Optional[str] = Field(None, description="Contact's full name")
    phone: Optional[str] = Field(None, description="Phone number")
    email: Optional[str] = Field(None, description="Email address")
    company: Optional[str] = Field(None, description="Company/Organization name")
    title: Optional[str] = Field(None, description="Job title/Position")
    industry: Optional[str] = Field(None, description="Industry/Sector")
    address: Optional[str] = Field(None, description="Business address")
    notes: Optional[str] = Field(None, description="Additional notes")
    source: Optional[str] = Field(None, description="Lead source")
    status: Optional[str] = Field(None, description="Contact status")
    category: Optional[ContactCategory] = Field(ContactCategory.PROSPECT, description="Contact category")


class ContactDataWithConfidence(ContactData):
    """Contact data with confidence scores for each field"""
    confidence_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Confidence score (0-1) for each extracted field"
    )
    overall_confidence: float = Field(0.0, description="Overall confidence score")
    confidence_level: ConfidenceLevel = Field(ConfidenceLevel.LOW, description="Confidence level category")


# ============ Spreadsheet Models ============

class ColumnMapping(BaseModel):
    """Column mapping for spreadsheet processing"""
    original_name: str = Field(..., description="Original column name from spreadsheet")
    mapped_to: Optional[str] = Field(None, description="Mapped field name (name, phone, email, etc.)")
    confidence: float = Field(0.0, description="Confidence of the mapping")
    sample_values: List[str] = Field(default_factory=list, description="Sample values from this column")


class DataQualityIssue(BaseModel):
    """Data quality issue found in spreadsheet"""
    row_number: int = Field(..., description="Row number with issue")
    column: str = Field(..., description="Column name")
    issue_type: str = Field(..., description="Type of issue (missing, invalid, duplicate)")
    description: str = Field(..., description="Description of the issue")
    suggested_fix: Optional[str] = Field(None, description="Suggested fix for the issue")


class DataQualityReport(BaseModel):
    """Data quality report for spreadsheet"""
    total_rows: int = Field(0, description="Total number of rows")
    valid_rows: int = Field(0, description="Number of valid rows")
    issues_count: int = Field(0, description="Total number of issues")
    issues: List[DataQualityIssue] = Field(default_factory=list, description="List of data quality issues")
    duplicate_count: int = Field(0, description="Number of duplicate entries")
    missing_phone_count: int = Field(0, description="Rows missing phone number")
    missing_name_count: int = Field(0, description="Rows missing name")
    quality_score: float = Field(0.0, description="Overall quality score (0-100)")


class SpreadsheetAnalysisRequest(BaseModel):
    """Request model for spreadsheet analysis"""
    filename: str = Field(..., description="Name of the uploaded file")
    preview_rows: int = Field(10, description="Number of rows to preview")


class SpreadsheetAnalysis(BaseModel):
    """Result of spreadsheet analysis"""
    filename: str = Field(..., description="Analyzed filename")
    total_rows: int = Field(0, description="Total number of data rows")
    total_columns: int = Field(0, description="Total number of columns")
    column_mappings: List[ColumnMapping] = Field(default_factory=list, description="Detected column mappings")
    quality_report: DataQualityReport = Field(default_factory=DataQualityReport, description="Data quality report")
    preview_data: List[Dict[str, Any]] = Field(default_factory=list, description="Preview of first few rows")
    status: ProcessingStatus = Field(ProcessingStatus.COMPLETED, description="Processing status")
    message: str = Field("", description="Status message")


class SpreadsheetProcessRequest(BaseModel):
    """Request model for spreadsheet processing"""
    filename: str = Field(..., description="Name of the uploaded file")
    column_mappings: Dict[str, str] = Field(..., description="User-confirmed column mappings")
    clean_phones: bool = Field(True, description="Clean and format phone numbers")
    remove_duplicates: bool = Field(True, description="Remove duplicate entries")
    auto_categorize: bool = Field(True, description="Auto-categorize contacts by industry")


class SpreadsheetProcessResult(BaseModel):
    """Result of spreadsheet processing"""
    total_processed: int = Field(0, description="Total rows processed")
    successful: int = Field(0, description="Successfully processed rows")
    failed: int = Field(0, description="Failed rows")
    duplicates_removed: int = Field(0, description="Duplicate entries removed")
    contacts: List[ContactData] = Field(default_factory=list, description="Processed contact data")
    status: ProcessingStatus = Field(ProcessingStatus.COMPLETED, description="Processing status")
    message: str = Field("", description="Status message")


# ============ Namecard/OCR Models ============

class NamecardScanRequest(BaseModel):
    """Request model for namecard scanning"""
    image_base64: Optional[str] = Field(None, description="Base64 encoded image")
    image_url: Optional[str] = Field(None, description="URL of the image")


class NamecardResult(BaseModel):
    """Result of namecard OCR processing"""
    contact: ContactDataWithConfidence = Field(..., description="Extracted contact information")
    raw_text: str = Field("", description="Raw OCR text")
    detected_language: str = Field("en", description="Detected language")
    processing_time_ms: int = Field(0, description="Processing time in milliseconds")
    status: ProcessingStatus = Field(ProcessingStatus.COMPLETED, description="Processing status")
    message: str = Field("", description="Status message")
    potential_duplicates: List[str] = Field(default_factory=list, description="IDs of potential duplicate contacts")


# ============ Chat Models ============

class ChatRole(str, Enum):
    """Chat message roles"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """Chat message model"""
    role: ChatRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Message timestamp")


class ChatQueryRequest(BaseModel):
    """Request model for chat queries"""
    query: str = Field(..., description="User's query")
    conversation_history: List[ChatMessage] = Field(default_factory=list, description="Previous conversation messages")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context (contacts, analytics, etc.)")
    user_id: Optional[str] = Field(None, description="User ID for personalization")


class ChatQueryResponse(BaseModel):
    """Response model for chat queries"""
    response: str = Field(..., description="AI response")
    query_type: str = Field("general", description="Type of query (contact_lookup, analytics, general, etc.)")
    referenced_contacts: List[str] = Field(default_factory=list, description="IDs of contacts referenced in response")
    suggested_actions: List[str] = Field(default_factory=list, description="Suggested follow-up actions")
    processing_time_ms: int = Field(0, description="Processing time in milliseconds")
    tokens_used: int = Field(0, description="Tokens used for this query")
    status: ProcessingStatus = Field(ProcessingStatus.COMPLETED, description="Processing status")


# ============ API Response Models ============

class APIResponse(BaseModel):
    """Standard API response wrapper"""
    success: bool = Field(True, description="Whether the request was successful")
    data: Optional[Any] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message if failed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str = Field("healthy", description="Service status")
    version: str = Field("1.0.0", description="API version")
    services: Dict[str, str] = Field(default_factory=dict, description="Status of dependent services")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
