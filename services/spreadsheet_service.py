"""
Spreadsheet processing service using Pandas
"""
import io
import re
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
from config import COLUMN_MAPPINGS, MALAYSIAN_PHONE_PATTERNS
from utils.phone_formatter import (
    format_malaysian_phone,
    validate_malaysian_phone,
    normalize_phone_for_comparison
)


class SpreadsheetService:
    """Service class for spreadsheet processing"""

    def __init__(self):
        """Initialize spreadsheet service"""
        self.column_mappings = COLUMN_MAPPINGS

    def read_spreadsheet(
        self,
        file_content: bytes,
        filename: str
    ) -> Tuple[pd.DataFrame, str]:
        """
        Read spreadsheet from file content

        Args:
            file_content: Raw file bytes
            filename: Name of the file

        Returns:
            Tuple of (DataFrame, error_message)
        """
        try:
            file_ext = filename.lower().split(".")[-1]

            if file_ext == "csv":
                # Try different encodings
                for encoding in ["utf-8", "latin-1", "cp1252"]:
                    try:
                        df = pd.read_csv(io.BytesIO(file_content), encoding=encoding)
                        return df, ""
                    except UnicodeDecodeError:
                        continue
                return pd.DataFrame(), "Could not decode CSV file"

            elif file_ext in ["xlsx", "xls"]:
                df = pd.read_excel(io.BytesIO(file_content))
                return df, ""

            else:
                return pd.DataFrame(), f"Unsupported file format: {file_ext}"

        except Exception as e:
            return pd.DataFrame(), str(e)

    def detect_columns(
        self,
        df: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """
        Auto-detect column types based on names and content

        Args:
            df: Pandas DataFrame

        Returns:
            List of column mapping results
        """
        results = []

        for col in df.columns:
            col_lower = str(col).lower().strip()
            sample_values = df[col].dropna().head(5).tolist()

            mapping = {
                "original_name": col,
                "mapped_to": None,
                "confidence": 0.0,
                "sample_values": [str(v) for v in sample_values]
            }

            # Try to match by column name
            for field_name, keywords in self.column_mappings.items():
                for keyword in keywords:
                    if keyword in col_lower or col_lower in keyword:
                        mapping["mapped_to"] = field_name
                        # Higher confidence for exact match
                        if col_lower == keyword:
                            mapping["confidence"] = 0.95
                        else:
                            mapping["confidence"] = 0.8
                        break
                if mapping["mapped_to"]:
                    break

            # If no name match, try content-based detection
            if not mapping["mapped_to"] and sample_values:
                mapping = self._detect_by_content(mapping, sample_values)

            results.append(mapping)

        return results

    def _detect_by_content(
        self,
        mapping: Dict[str, Any],
        sample_values: List
    ) -> Dict[str, Any]:
        """
        Detect column type by analyzing content

        Args:
            mapping: Current mapping dict
            sample_values: Sample values from the column

        Returns:
            Updated mapping dict
        """
        sample_strings = [str(v) for v in sample_values if v is not None]

        if not sample_strings:
            return mapping

        # Check for email pattern
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        email_count = sum(1 for s in sample_strings if re.match(email_pattern, s))
        if email_count >= len(sample_strings) * 0.6:
            mapping["mapped_to"] = "email"
            mapping["confidence"] = 0.9
            return mapping

        # Check for phone pattern
        phone_patterns = [
            r"^\+?60[\d\s\-]+$",  # Malaysian
            r"^0\d[\d\s\-]+$",    # Local format
            r"^[\d\s\-\+\(\)]{8,}$"  # General phone
        ]
        phone_count = 0
        for s in sample_strings:
            for pattern in phone_patterns:
                if re.match(pattern, s.strip()):
                    phone_count += 1
                    break

        if phone_count >= len(sample_strings) * 0.6:
            mapping["mapped_to"] = "phone"
            mapping["confidence"] = 0.85
            return mapping

        # Check for name-like content (2-4 words, alphabetic)
        name_count = sum(1 for s in sample_strings
                        if 2 <= len(s.split()) <= 5 and
                        re.match(r"^[a-zA-Z\s\.\'\-]+$", s))
        if name_count >= len(sample_strings) * 0.6:
            mapping["mapped_to"] = "name"
            mapping["confidence"] = 0.7
            return mapping

        return mapping

    def clean_data(
        self,
        df: pd.DataFrame,
        column_mappings: Dict[str, str],
        clean_phones: bool = True
    ) -> pd.DataFrame:
        """
        Clean and normalize data based on column mappings

        Args:
            df: Input DataFrame
            column_mappings: Mapping of original columns to standard fields
            clean_phones: Whether to clean phone numbers

        Returns:
            Cleaned DataFrame
        """
        cleaned_df = df.copy()

        # Rename columns to standard names
        rename_map = {orig: std for orig, std in column_mappings.items() if std}
        cleaned_df = cleaned_df.rename(columns=rename_map)

        # Clean phone numbers
        if clean_phones and "phone" in cleaned_df.columns:
            cleaned_df["phone"] = cleaned_df["phone"].apply(self._clean_phone)

        # Clean email addresses
        if "email" in cleaned_df.columns:
            cleaned_df["email"] = cleaned_df["email"].apply(self._clean_email)

        # Clean names
        if "name" in cleaned_df.columns:
            cleaned_df["name"] = cleaned_df["name"].apply(self._clean_name)

        # Strip whitespace from all string columns
        for col in cleaned_df.select_dtypes(include=["object"]).columns:
            cleaned_df[col] = cleaned_df[col].apply(
                lambda x: str(x).strip() if pd.notna(x) else None
            )

        return cleaned_df

    def _clean_phone(self, phone: Any) -> Optional[str]:
        """Clean a single phone number"""
        if pd.isna(phone):
            return None

        phone_str = str(phone).strip()

        # Try to format as Malaysian number
        formatted = format_malaysian_phone(phone_str)
        if formatted:
            return formatted

        # If not Malaysian, just clean up
        cleaned = re.sub(r"[^\d\+]", "", phone_str)
        return cleaned if len(cleaned) >= 8 else None

    def _clean_email(self, email: Any) -> Optional[str]:
        """Clean a single email address"""
        if pd.isna(email):
            return None

        email_str = str(email).strip().lower()

        # Validate email format
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if re.match(email_pattern, email_str):
            return email_str

        return None

    def _clean_name(self, name: Any) -> Optional[str]:
        """Clean a single name"""
        if pd.isna(name):
            return None

        name_str = str(name).strip()

        # Title case, preserving honorifics
        words = name_str.split()
        cleaned_words = []

        honorifics = ["dr", "dr.", "dato'", "datuk", "tan sri", "tun", "datin", "mr", "mrs", "ms", "prof"]

        for word in words:
            word_lower = word.lower()
            if word_lower in honorifics or word.isupper():
                # Preserve honorifics and all-caps (might be intentional)
                cleaned_words.append(word)
            else:
                cleaned_words.append(word.title())

        return " ".join(cleaned_words) if cleaned_words else None

    def validate_data(
        self,
        df: pd.DataFrame,
        column_mappings: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Validate data quality and report issues

        Args:
            df: DataFrame to validate
            column_mappings: Column mappings

        Returns:
            Validation report
        """
        issues = []
        total_rows = len(df)

        # Map to standard column names
        std_columns = {std: orig for orig, std in column_mappings.items() if std}

        # Check for missing names
        missing_names = 0
        if "name" in std_columns:
            name_col = std_columns["name"]
            missing_names = df[name_col].isna().sum()
            for idx in df[df[name_col].isna()].index:
                issues.append({
                    "row_number": int(idx) + 2,  # +2 for header and 0-index
                    "column": name_col,
                    "issue_type": "missing",
                    "description": "Missing contact name",
                    "suggested_fix": "Add contact name or remove row"
                })

        # Check for missing phones
        missing_phones = 0
        invalid_phones = 0
        if "phone" in std_columns:
            phone_col = std_columns["phone"]
            missing_phones = df[phone_col].isna().sum()

            for idx, row in df.iterrows():
                phone = row[phone_col]
                if pd.notna(phone):
                    is_valid, msg = validate_malaysian_phone(str(phone))
                    if not is_valid:
                        invalid_phones += 1
                        issues.append({
                            "row_number": int(idx) + 2,
                            "column": phone_col,
                            "issue_type": "invalid",
                            "description": f"Invalid phone: {msg}",
                            "suggested_fix": "Format as Malaysian number (+60 XX-XXX XXXX)"
                        })

        # Check for invalid emails
        invalid_emails = 0
        if "email" in std_columns:
            email_col = std_columns["email"]
            email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

            for idx, row in df.iterrows():
                email = row[email_col]
                if pd.notna(email) and not re.match(email_pattern, str(email).strip()):
                    invalid_emails += 1
                    issues.append({
                        "row_number": int(idx) + 2,
                        "column": email_col,
                        "issue_type": "invalid",
                        "description": "Invalid email format",
                        "suggested_fix": "Check email address format"
                    })

        # Calculate quality score
        total_fields = total_rows * len(column_mappings)
        issue_count = len(issues)
        quality_score = max(0, 100 - (issue_count / max(1, total_fields) * 100))

        return {
            "total_rows": total_rows,
            "valid_rows": total_rows - missing_names,
            "issues_count": issue_count,
            "issues": issues[:100],  # Limit to first 100 issues
            "duplicate_count": 0,  # Will be filled by deduplicate
            "missing_phone_count": missing_phones,
            "missing_name_count": missing_names,
            "invalid_phone_count": invalid_phones,
            "invalid_email_count": invalid_emails,
            "quality_score": round(quality_score, 1)
        }

    def deduplicate(
        self,
        df: pd.DataFrame,
        column_mappings: Dict[str, str]
    ) -> Tuple[pd.DataFrame, int, List[Dict]]:
        """
        Find and remove duplicate entries

        Args:
            df: DataFrame to deduplicate
            column_mappings: Column mappings

        Returns:
            Tuple of (deduplicated_df, duplicate_count, duplicate_groups)
        """
        if df.empty:
            return df, 0, []

        std_columns = {std: orig for orig, std in column_mappings.items() if std}

        # Build dedup key based on available columns
        dedup_columns = []

        # Phone is best for dedup
        if "phone" in std_columns:
            phone_col = std_columns["phone"]
            df["_phone_normalized"] = df[phone_col].apply(
                lambda x: normalize_phone_for_comparison(str(x)) if pd.notna(x) else ""
            )
            dedup_columns.append("_phone_normalized")

        # Email as secondary
        if "email" in std_columns:
            email_col = std_columns["email"]
            df["_email_normalized"] = df[email_col].apply(
                lambda x: str(x).lower().strip() if pd.notna(x) else ""
            )
            dedup_columns.append("_email_normalized")

        # Name as fallback
        if "name" in std_columns and not dedup_columns:
            name_col = std_columns["name"]
            df["_name_normalized"] = df[name_col].apply(
                lambda x: str(x).lower().strip() if pd.notna(x) else ""
            )
            dedup_columns.append("_name_normalized")

        if not dedup_columns:
            return df, 0, []

        # Find duplicates
        duplicate_groups = []
        original_count = len(df)

        # Group by dedup columns
        for col in dedup_columns:
            duplicates = df[df.duplicated(subset=[col], keep=False) & (df[col] != "")]
            for value, group in duplicates.groupby(col):
                if len(group) > 1 and value:
                    duplicate_groups.append({
                        "key": col.replace("_normalized", "").replace("_", ""),
                        "value": value,
                        "count": len(group),
                        "row_numbers": (group.index + 2).tolist()
                    })

        # Remove duplicates (keep first)
        deduped_df = df.drop_duplicates(subset=dedup_columns, keep="first")

        # Clean up temp columns
        for col in ["_phone_normalized", "_email_normalized", "_name_normalized"]:
            if col in deduped_df.columns:
                deduped_df = deduped_df.drop(columns=[col])
            if col in df.columns:
                df = df.drop(columns=[col])

        duplicate_count = original_count - len(deduped_df)

        return deduped_df, duplicate_count, duplicate_groups[:50]

    def to_contact_list(
        self,
        df: pd.DataFrame,
        column_mappings: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Convert DataFrame to list of contact dictionaries

        Args:
            df: Cleaned DataFrame
            column_mappings: Column mappings

        Returns:
            List of contact dictionaries
        """
        contacts = []

        # Build reverse mapping
        std_to_orig = {std: orig for orig, std in column_mappings.items() if std}

        for _, row in df.iterrows():
            contact = {}

            for std_field, orig_col in std_to_orig.items():
                value = row.get(orig_col)
                if pd.notna(value):
                    contact[std_field] = str(value)
                else:
                    contact[std_field] = None

            # Only add if has at least name or phone
            if contact.get("name") or contact.get("phone"):
                contacts.append(contact)

        return contacts


# Create singleton instance
spreadsheet_service = SpreadsheetService()
