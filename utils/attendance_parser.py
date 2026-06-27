from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict
import re
import pandas as pd


@dataclass
class AttendanceIssue:
    """A single attendance issue row."""
    date: str
    reason: str


@dataclass
class EmployeeRecord:
    """Employee attendance data."""
    name: str
    code: str
    issues: list = field(default_factory=list)


ISSUE_KEYWORDS = {
    "missing in": "Missing In Punch",
    "missing out": "Missing Out Punch",
    "early out": "Early Out",
    "invalid": "Invalid Punch",
    "mispunch": "Mispunch",
    "miss punch": "Mispunch",
    "technical": "Technical Error",
}

TECHNICAL_ERROR = "Technical Error"
PUNCH_REASONS = {"Missing In Punch", "Missing Out Punch", "Invalid Punch", "Mispunch"}
EARLY_OUT_REASON = "Early Out"


def parse_attendance_file(path):
    """Parse Excel or image/PDF file."""
    extension = Path(path).suffix.lower()
    
    if extension in {".xlsx", ".xls"}:
        records = _parse_excel(path)
        month = _guess_month_from_records(records)
        return records, month
    
    # For image/PDF, extract via OCR in app.py
    from utils.ocr import extract_text_from_image_or_pdf
    text = extract_text_from_image_or_pdf(path)
    records = _parse_ocr_text(text)
    month = _guess_month_from_records(records)
    return records, month


def _parse_excel(path):
    """Read Excel file using pandas."""
    workbook = pd.read_excel(path, sheet_name=None)
    employees = {}
    
    for _, frame in workbook.items():
        if frame.empty:
            continue
        
        frame = _clean_dataframe(frame)
        columns = _map_columns(frame.columns)
        
        for _, row in frame.iterrows():
            name = _read_cell(row, columns.get("name"))
            code = _read_cell(row, columns.get("code"))
            date = _read_cell(row, columns.get("date"))
            reason = _read_reason(row, columns)
            
            if not name and not code:
                continue
            
            employee_key = code or name
            record = employees.setdefault(
                employee_key,
                EmployeeRecord(name=name or "Unknown", code=code or "N/A"),
            )
            
            if date and reason:
                record.issues.append(AttendanceIssue(date=_format_date(date), reason=reason))
    
    return list(employees.values())


def _clean_dataframe(frame):
    """Clean dataframe."""
    frame = frame.dropna(how="all").dropna(axis=1, how="all")
    frame.columns = [str(col).strip() for col in frame.columns]
    return frame.fillna("")


def _map_columns(columns):
    """Map columns to standard names."""
    mapping = {}
    
    for column in columns:
        normalized = _normalize(column)
        if "name" in normalized and "employee" in normalized:
            mapping["name"] = column
        elif normalized in {"name", "emp name", "employee"}:
            mapping["name"] = column
        elif "code" in normalized or "id" in normalized:
            mapping["code"] = column
        elif "date" in normalized or "day" == normalized:
            mapping["date"] = column
        elif any(x in normalized for x in ["reason", "remarks", "status", "attendance", "issue", "exception"]):
            mapping["reason"] = column
    
    return mapping


def _read_cell(row, column):
    """Safely read cell value."""
    if not column or column not in row:
        return ""
    value = row[column]
    if pd.isna(value):
        return ""
    return str(value).strip()


def _read_reason(row, columns):
    """Read reason or scan row for keywords."""
    reason = _standardize_reason(_read_cell(row, columns.get("reason")))
    if reason:
        return reason
    joined_row = " ".join(str(value) for value in row.values if str(value).strip())
    return _standardize_reason(joined_row)


def _parse_ocr_text(text):
    """Parse OCR extracted text."""
    employees = {}
    current_key = None
    
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        
        name = _extract_label(line, ["employee name", "emp name", "name"])
        code = _extract_label(line, ["employee code", "emp code", "code"])
        
        if name or code:
            current_key = code or name or f"employee-{len(employees) + 1}"
            record = employees.setdefault(
                current_key,
                EmployeeRecord(name=name or "Unknown", code=code or "N/A"),
            )
            if name:
                record.name = name
            if code:
                record.code = code
            continue
        
        reason = _standardize_reason(line)
        date = _extract_date(line)
        
        if reason and date:
            if current_key is None:
                current_key = "unknown"
                employees[current_key] = EmployeeRecord(name="Unknown", code="N/A")
            employees[current_key].issues.append(AttendanceIssue(date=date, reason=reason))
    
    return list(employees.values())


def _extract_label(line, labels):
    """Extract label value like 'Employee Name: John'."""
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:\-]\s*(.+)$"
        match = re.search(pattern, line, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _extract_date(line):
    """Find date in text."""
    patterns = [
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
        r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}\b",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, line)
        if match:
            return _format_date(match.group(0))
    
    return ""


def _standardize_reason(value):
    """Convert text to standard reason."""
    normalized = _normalize(value)
    
    for keyword, reason in ISSUE_KEYWORDS.items():
        if keyword in normalized:
            return reason
    
    return ""


def _format_date(value):
    """Format date consistently."""
    parsed = _parse_date(value)
    if parsed:
        return parsed.strftime("%d-%m-%Y")
    return str(value).strip()


def _parse_date(value):
    """Try multiple date formats."""
    if isinstance(value, (pd.Timestamp,)):
        return value.to_pydatetime()
    
    text = str(value).strip()
    for dayfirst in (True, False):
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=dayfirst)
        if not pd.isna(parsed):
            return parsed.to_pydatetime()
    
    return None


def _guess_month_from_records(records):
    """Get month from first attendance date."""
    for record in records:
        for issue in record.issues:
            parsed = _parse_date(issue.date)
            if parsed:
                return parsed.strftime("%B %Y")
    return datetime.now().strftime("%B %Y")


def _normalize(value):
    """Normalize text for matching."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-zA-Z0-9]+", " ", str(value))).strip().lower()


def apply_attendance_limits(issues):
    """
    Apply HR rules:
    - Max 3 Mispunch
    - Max 3 Early Out
    - Additional becomes Technical Error
    """
    counts = defaultdict(int)
    limited_issues = []
    
    for issue in issues:
        reason = issue.reason
        
        if reason in PUNCH_REASONS:
            counts["mispunch"] += 1
            if counts["mispunch"] > 3:
                reason = TECHNICAL_ERROR
        
        if reason == EARLY_OUT_REASON:
            counts["early_out"] += 1
            if counts["early_out"] > 3:
                reason = TECHNICAL_ERROR
        
        limited_issues.append(AttendanceIssue(date=issue.date, reason=reason))
    
    return limited_issues
