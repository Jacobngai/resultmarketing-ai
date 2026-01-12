"""
Models package for ResultMarketing AI Microservice
"""
from .schemas import (
    ProcessingStatus,
    ConfidenceLevel,
    ContactCategory,
    ContactData,
    ContactDataWithConfidence,
    ColumnMapping,
    DataQualityIssue,
    DataQualityReport,
    SpreadsheetAnalysisRequest,
    SpreadsheetAnalysis,
    SpreadsheetProcessRequest,
    SpreadsheetProcessResult,
    NamecardScanRequest,
    NamecardResult,
    ChatRole,
    ChatMessage,
    ChatQueryRequest,
    ChatQueryResponse,
    APIResponse,
    HealthCheckResponse
)

__all__ = [
    "ProcessingStatus",
    "ConfidenceLevel",
    "ContactCategory",
    "ContactData",
    "ContactDataWithConfidence",
    "ColumnMapping",
    "DataQualityIssue",
    "DataQualityReport",
    "SpreadsheetAnalysisRequest",
    "SpreadsheetAnalysis",
    "SpreadsheetProcessRequest",
    "SpreadsheetProcessResult",
    "NamecardScanRequest",
    "NamecardResult",
    "ChatRole",
    "ChatMessage",
    "ChatQueryRequest",
    "ChatQueryResponse",
    "APIResponse",
    "HealthCheckResponse"
]
