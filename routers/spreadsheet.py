"""
Spreadsheet analysis and processing endpoints
"""
import time
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from pydantic import BaseModel

from models.schemas import (
    SpreadsheetAnalysis,
    SpreadsheetProcessResult,
    ColumnMapping,
    DataQualityReport,
    DataQualityIssue,
    ProcessingStatus,
    APIResponse
)
from services.spreadsheet_service import spreadsheet_service
from services.claude_service import claude_service


router = APIRouter(prefix="/api/spreadsheet", tags=["Spreadsheet"])


class ProcessRequest(BaseModel):
    """Request body for spreadsheet processing"""
    column_mappings: Dict[str, str]
    clean_phones: bool = True
    remove_duplicates: bool = True
    auto_categorize: bool = True


# Store uploaded files temporarily (in production, use Redis or file storage)
_temp_storage: Dict[str, bytes] = {}


@router.post("/analyze", response_model=APIResponse)
async def analyze_spreadsheet(
    file: UploadFile = File(...),
    preview_rows: int = 10
):
    """
    Analyze uploaded spreadsheet and return column mappings and data quality report

    - Detects column types (name, phone, email, company, etc.)
    - Reports data quality issues
    - Provides preview of data
    """
    start_time = time.time()

    try:
        # Validate file type
        filename = file.filename
        if not filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        file_ext = filename.lower().split(".")[-1]
        if file_ext not in ["csv", "xlsx", "xls"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_ext}. Use CSV or Excel files."
            )

        # Read file content
        file_content = await file.read()

        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        # Store temporarily for processing
        _temp_storage[filename] = file_content

        # Read spreadsheet
        df, error = spreadsheet_service.read_spreadsheet(file_content, filename)

        if error:
            raise HTTPException(status_code=400, detail=f"Error reading file: {error}")

        if df.empty:
            raise HTTPException(status_code=400, detail="Spreadsheet is empty")

        # Detect columns
        column_mappings = spreadsheet_service.detect_columns(df)

        # Build column mapping dict for validation
        mapping_dict = {m["original_name"]: m["mapped_to"] for m in column_mappings}

        # Validate data
        quality_report_data = spreadsheet_service.validate_data(df, mapping_dict)

        # Convert to Pydantic models
        column_mapping_models = [
            ColumnMapping(
                original_name=m["original_name"],
                mapped_to=m["mapped_to"],
                confidence=m["confidence"],
                sample_values=m["sample_values"][:5]
            )
            for m in column_mappings
        ]

        quality_issues = [
            DataQualityIssue(
                row_number=issue["row_number"],
                column=issue["column"],
                issue_type=issue["issue_type"],
                description=issue["description"],
                suggested_fix=issue.get("suggested_fix")
            )
            for issue in quality_report_data.get("issues", [])[:50]
        ]

        quality_report = DataQualityReport(
            total_rows=quality_report_data["total_rows"],
            valid_rows=quality_report_data["valid_rows"],
            issues_count=quality_report_data["issues_count"],
            issues=quality_issues,
            duplicate_count=quality_report_data.get("duplicate_count", 0),
            missing_phone_count=quality_report_data["missing_phone_count"],
            missing_name_count=quality_report_data["missing_name_count"],
            quality_score=quality_report_data["quality_score"]
        )

        # Get preview data
        preview_df = df.head(preview_rows)
        preview_data = preview_df.to_dict(orient="records")

        # Use Claude to enhance analysis if API key is configured
        ai_analysis = None
        try:
            if claude_service.client:
                ai_analysis = claude_service.analyze_spreadsheet(
                    columns=list(df.columns),
                    sample_data=preview_data[:5],
                    row_count=len(df)
                )
        except Exception as e:
            # AI analysis is optional, continue without it
            ai_analysis = {"error": str(e)}

        result = SpreadsheetAnalysis(
            filename=filename,
            total_rows=len(df),
            total_columns=len(df.columns),
            column_mappings=column_mapping_models,
            quality_report=quality_report,
            preview_data=preview_data,
            status=ProcessingStatus.COMPLETED,
            message=f"Analysis completed in {int((time.time() - start_time) * 1000)}ms"
        )

        return APIResponse(
            success=True,
            data={
                "analysis": result.model_dump(),
                "ai_insights": ai_analysis
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process", response_model=APIResponse)
async def process_spreadsheet(
    filename: str = Form(...),
    column_mappings: str = Form(...),
    clean_phones: bool = Form(True),
    remove_duplicates: bool = Form(True),
    auto_categorize: bool = Form(True)
):
    """
    Process spreadsheet with confirmed column mappings

    - Cleans and normalizes data
    - Removes duplicates if requested
    - Auto-categorizes contacts by industry
    - Returns cleaned contact data ready for import
    """
    import json
    start_time = time.time()

    try:
        # Parse column mappings JSON
        try:
            mappings = json.loads(column_mappings)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid column_mappings JSON")

        # Get stored file
        if filename not in _temp_storage:
            raise HTTPException(
                status_code=400,
                detail="File not found. Please upload and analyze first."
            )

        file_content = _temp_storage[filename]

        # Read spreadsheet
        df, error = spreadsheet_service.read_spreadsheet(file_content, filename)

        if error:
            raise HTTPException(status_code=400, detail=f"Error reading file: {error}")

        # Clean data
        cleaned_df = spreadsheet_service.clean_data(
            df,
            mappings,
            clean_phones=clean_phones
        )

        # Deduplicate if requested
        duplicates_removed = 0
        duplicate_groups = []
        if remove_duplicates:
            cleaned_df, duplicates_removed, duplicate_groups = spreadsheet_service.deduplicate(
                cleaned_df,
                mappings
            )

        # Convert to contact list
        contacts = spreadsheet_service.to_contact_list(cleaned_df, mappings)

        # Auto-categorize using Claude if requested
        if auto_categorize:
            try:
                for i, contact in enumerate(contacts[:100]):  # Limit to first 100 for cost
                    if contact.get("company") or contact.get("name"):
                        categorization = claude_service.categorize_contact(contact)
                        if not categorization.get("parse_error"):
                            contacts[i]["industry"] = categorization.get("industry", "other")
                            contacts[i]["category"] = categorization.get("contact_type", "prospect")
                            contacts[i]["priority"] = categorization.get("priority", "medium")
            except Exception as e:
                # Categorization is optional, continue without it
                pass

        # Clean up temp storage
        del _temp_storage[filename]

        result = SpreadsheetProcessResult(
            total_processed=len(df),
            successful=len(contacts),
            failed=len(df) - len(contacts),
            duplicates_removed=duplicates_removed,
            contacts=[],  # Don't include full list in response to save bandwidth
            status=ProcessingStatus.COMPLETED,
            message=f"Processed {len(contacts)} contacts in {int((time.time() - start_time) * 1000)}ms"
        )

        return APIResponse(
            success=True,
            data={
                "summary": result.model_dump(),
                "contacts": contacts,
                "duplicate_groups": duplicate_groups
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=APIResponse)
async def validate_spreadsheet(file: UploadFile = File(...)):
    """
    Quick validation of spreadsheet without full processing

    - Checks file format
    - Validates structure
    - Returns basic statistics
    """
    try:
        filename = file.filename
        if not filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        file_ext = filename.lower().split(".")[-1]
        if file_ext not in ["csv", "xlsx", "xls"]:
            return APIResponse(
                success=False,
                error=f"Unsupported file type: {file_ext}"
            )

        file_content = await file.read()

        if len(file_content) == 0:
            return APIResponse(
                success=False,
                error="Empty file"
            )

        df, error = spreadsheet_service.read_spreadsheet(file_content, filename)

        if error:
            return APIResponse(
                success=False,
                error=f"Cannot read file: {error}"
            )

        return APIResponse(
            success=True,
            data={
                "valid": True,
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": list(df.columns),
                "file_size_bytes": len(file_content)
            }
        )

    except Exception as e:
        return APIResponse(
            success=False,
            error=str(e)
        )
