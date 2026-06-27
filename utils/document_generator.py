import shutil
from pathlib import Path
from datetime import datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def build_employee_documents(records, output_dir, output_format, company_name, month):
    """Create one form per employee and bundle everything in a ZIP file."""
    output_dir = Path(output_dir)
    forms_dir = output_dir / "forms"
    forms_dir.mkdir(parents=True, exist_ok=True)

    for record in records:
        docx_path = forms_dir / f"{_safe_filename(record.code)}_{_safe_filename(record.name)}.docx"
        _create_docx(record, docx_path, company_name, month)

        if output_format == "pdf":
            _convert_docx_to_pdf(docx_path)
            docx_path.unlink(missing_ok=True)

    zip_base = output_dir / "attendance_forms"
    return shutil.make_archive(str(zip_base), "zip", forms_dir)


def create_single_docx(record, path, company_name, month, department=""):
    """
    Create a single Word document for manual entry.
    
    Args:
        record: EmployeeRecord object
        path: Output file path
        company_name: Company name
        month: Month string (e.g., "June 2026")
        department: Department name (optional)
    """
    _create_docx(record, path, company_name, month, department)


def _create_docx(record, path, company_name, month, department=""):
    """Build the employee attendance correction form."""
    document = Document()

    # Set margins
    for section in document.sections:
        section.top_margin = Inches(0.7)
        section.bottom_margin = Inches(0.7)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Company name (title)
    title = document.add_heading(company_name, level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Form title
    subtitle = document.add_paragraph("Attendance Correction Form")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.runs[0].bold = True
    subtitle.runs[0].font.size = Pt(14)

    # Employee details
    document.add_paragraph(f"Employee Name: {record.name}")
    document.add_paragraph(f"Employee Code: {record.code}")
    if department:
        document.add_paragraph(f"Department: {department}")
    document.add_paragraph(f"Month: {month}")
    document.add_paragraph(f"Date: {datetime.now().strftime('%d-%m-%Y')}")

    # Attendance issues table
    table = document.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    
    # Header row
    header_cells = table.rows[0].cells
    header_cells[0].text = "S.No"
    header_cells[1].text = "Date"
    header_cells[2].text = "Reason"
    
    # Make header bold
    for cell in header_cells:
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True

    # Data rows
    for index, issue in enumerate(record.issues, start=1):
        row_cells = table.add_row().cells
        row_cells[0].text = str(index)
        row_cells[1].text = issue.date
        row_cells[2].text = issue.reason

    # Spacing
    document.add_paragraph("")
    document.add_paragraph("")

    # Signature section
    signature_table = document.add_table(rows=2, cols=2)
    signature_table.style = "Table Grid"
    
    # Row 1: Labels
    sig_cells = signature_table.rows[0].cells
    sig_cells[0].text = "Employee Signature"
    sig_cells[1].text = "HR Signature"
    
    # Row 2: Space for signatures
    sig_cells = signature_table.rows[1].cells
    sig_cells[0].text = "_" * 30
    sig_cells[1].text = "_" * 30

    document.save(path)


def _convert_docx_to_pdf(docx_path):
    """Convert Word to PDF when docx2pdf and Microsoft Word/LibreOffice are available."""
    try:
        from docx2pdf import convert

        convert(str(docx_path), str(docx_path.with_suffix(".pdf")))
        return
    except Exception:
        pass

    try:
        import subprocess

        subprocess.run(
            [
                "soffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(docx_path.parent),
                str(docx_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return
    except Exception as exc:
        raise RuntimeError(
            "PDF output needs Microsoft Word with docx2pdf or LibreOffice installed."
        ) from exc


def _safe_filename(value):
    """Keep generated file names portable across operating systems."""
    cleaned = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in str(value))
    return cleaned.strip("_") or "employee"
