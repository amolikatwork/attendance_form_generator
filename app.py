import shutil
import uuid
import traceback
import logging
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename

from utils.attendance_parser import parse_attendance_file, EmployeeRecord, AttendanceIssue
from utils.document_generator import build_employee_documents, create_single_docx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Flask keeps the web routes small; parsing and document generation live in utils.
app = Flask(__name__)
app.config["SECRET_KEY"] = "attendance-form-generator"
app.config["UPLOAD_FOLDER"] = Path("uploads")
app.config["OUTPUT_FOLDER"] = Path("outputs")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".png", ".jpg", ".jpeg", ".pdf"}
OUTPUT_FORMATS = {"docx", "pdf"}

REASON_OPTIONS = [
    "Mispunch",
    "Missing In Punch",
    "Missing Out Punch",
    "Early Out",
    "Technical Error",
    "Invalid Punch"
]


def ensure_project_folders():
    """Create runtime folders if this is the first launch."""
    app.config["UPLOAD_FOLDER"].mkdir(exist_ok=True)
    app.config["OUTPUT_FOLDER"].mkdir(exist_ok=True)
    Path("static").mkdir(exist_ok=True)


def allowed_file(filename):
    """Validate uploads by extension before saving them."""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET", "POST"])
def index():
    """Homepage with navigation to Manual Entry, Upload Excel, and Upload Image."""
    ensure_project_folders()
    
    if request.method == "GET":
        return render_template("index.html")

    # Original upload route logic
    try:
        logger.info("[UPLOAD] Request received")
        
        uploaded_file = request.files.get("attendance_file")
        output_format = request.form.get("output_format", "docx").lower()
        company_name = request.form.get("company_name", "Company Name").strip() or "Company Name"

        logger.info(f"[UPLOAD] Form data parsed: company_name={company_name}, output_format={output_format}")

        if not uploaded_file or uploaded_file.filename == "":
            return render_template("index.html", error="Please upload an attendance file.")

        if not allowed_file(uploaded_file.filename):
            return render_template(
                "index.html",
                error="Upload a .xlsx, .xls, .png, .jpg, .jpeg, or .pdf file.",
            )

        if output_format not in OUTPUT_FORMATS:
            return render_template("index.html", error="Choose a valid output format.")

        job_id = uuid.uuid4().hex
        safe_name = secure_filename(uploaded_file.filename)
        upload_path = app.config["UPLOAD_FOLDER"] / f"{job_id}_{safe_name}"
        job_output_dir = app.config["OUTPUT_FOLDER"] / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)

        uploaded_file.save(upload_path)
        logger.info(f"[UPLOAD] File saved: {upload_path}")

        logger.info("[UPLOAD] Starting parsing")
        records, month = parse_attendance_file(upload_path)
        logger.info(f"[UPLOAD] Parsing complete. Found {len(records)} records. Month: {month}")
        
        if not records:
            raise ValueError("No employee attendance records were found.")

        logger.info("[UPLOAD] Word generation started")
        zip_path = build_employee_documents(
            records=records,
            output_dir=job_output_dir,
            output_format=output_format,
            company_name=company_name,
            month=month,
        )
        logger.info(f"[UPLOAD] Word saved successfully")
        logger.info(f"[UPLOAD] Returning file")

        return send_file(zip_path, as_attachment=True, download_name="attendance_forms.zip")

    except Exception as exc:
        logger.error(f"[UPLOAD] EXCEPTION OCCURRED")
        logger.error(traceback.format_exc())
        shutil.rmtree(job_output_dir, ignore_errors=True)
        return render_template("index.html", error=f"Could not generate forms: {exc}")


@app.route("/manual", methods=["GET", "POST"])
def manual_entry():
    """Manual entry page for creating attendance correction forms."""
    ensure_project_folders()
    
    if request.method == "GET":
        logger.info("[MANUAL] GET request - rendering manual entry form")
        return render_template("manual.html", reason_options=REASON_OPTIONS)
    
    # POST request: Generate Word document from manual entry
    try:
        logger.info("[MANUAL] Request received")
        
        # Parse form data
        company_name = request.form.get("company_name", "Company Name").strip() or "Company Name"
        company_logo = request.files.get("company_logo", None)
        employee_name = request.form.get("employee_name", "").strip()
        employee_code = request.form.get("employee_code", "").strip()
        department = request.form.get("department", "").strip()
        month = request.form.get("month", datetime.now().strftime("%B %Y")).strip()
        
        logger.info(f"[MANUAL] Employee information received: {employee_name} ({employee_code}), Dept: {department}, Month: {month}")
        
        # Validate required fields
        if not employee_name or not employee_code:
            return render_template("manual.html", reason_options=REASON_OPTIONS, 
                                 error="Employee Name and Code are required.")
        
        # Parse attendance rows
        attendance_dates = request.form.getlist("attendance_date[]")
        attendance_reasons = request.form.getlist("attendance_reason[]")
        
        issues = []
        for date_str, reason in zip(attendance_dates, attendance_reasons):
            if date_str and reason:
                issues.append(AttendanceIssue(date=date_str, reason=reason))
        
        logger.info(f"[MANUAL] Attendance rows parsed: {len(issues)} rows")
        
        if not issues:
            return render_template("manual.html", reason_options=REASON_OPTIONS,
                                 error="Please add at least one attendance issue.")
        
        # Create employee record
        employee = EmployeeRecord(name=employee_name, code=employee_code, issues=issues)
        
        # Generate document
        logger.info("[MANUAL] Word generation started")
        
        job_id = uuid.uuid4().hex
        job_output_dir = app.config["OUTPUT_FOLDER"] / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)
        
        docx_path = job_output_dir / f"{employee_code}_{employee_name}.docx"
        
        create_single_docx(
            employee,
            docx_path,
            company_name,
            month,
            department
        )
        
        logger.info(f"[MANUAL] Word document saved: {docx_path}")
        logger.info("[MANUAL] Sending file to user")
        
        return send_file(
            docx_path,
            as_attachment=True,
            download_name=f"{employee_code}_{employee_name}.docx"
        )
    
    except Exception as exc:
        logger.error("[MANUAL] EXCEPTION OCCURRED")
        logger.error(traceback.format_exc())
        return render_template("manual.html", reason_options=REASON_OPTIONS,
                             error=f"Error generating document: {exc}")


if __name__ == "__main__":
    ensure_project_folders()
    app.run(debug=True)
