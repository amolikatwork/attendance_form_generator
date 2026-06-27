import shutil
import uuid
import traceback
import logging
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, send_file, session, jsonify
from werkzeug.utils import secure_filename

from utils.attendance_parser import parse_attendance_file, EmployeeRecord, AttendanceIssue, apply_attendance_limits
from utils.document_generator import create_single_docx, convert_to_pdf
from utils.ocr import extract_text_from_image_or_pdf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
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
    """Create runtime folders."""
    app.config["UPLOAD_FOLDER"].mkdir(exist_ok=True)
    app.config["OUTPUT_FOLDER"].mkdir(exist_ok=True)
    Path("static").mkdir(exist_ok=True)


def allowed_file(filename):
    """Validate uploads by extension."""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET"])
def index():
    """Home page with 3 modules."""
    ensure_project_folders()
    logger.info("[HOME] GET / - Rendering home page")
    return render_template("home.html")


@app.route("/manual", methods=["GET"])
def manual():
    """Manual entry page."""
    ensure_project_folders()
    logger.info("[MANUAL] GET /manual - Rendering manual entry form")
    return render_template("manual.html", reason_options=REASON_OPTIONS)


@app.route("/generate", methods=["POST"])
def generate():
    """Generate Word or PDF document from manual entry."""
    ensure_project_folders()
    job_output_dir = None
    docx_path = None
    
    try:
        logger.info("[MANUAL] POST /generate - Request received")
        
        # Parse form data
        company_name = request.form.get("company_name", "Company Name").strip() or "Company Name"
        employee_name = request.form.get("employee_name", "").strip()
        employee_code = request.form.get("employee_code", "").strip()
        department = request.form.get("department", "").strip()
        month = request.form.get("month", datetime.now().strftime("%B %Y")).strip()
        output_format = request.form.get("output_format", "docx").lower()
        
        logger.info(f"[MANUAL] Employee info: {employee_name} ({employee_code}), Dept: {department}, Month: {month}, Format: {output_format}")
        
        # Validate
        if not employee_name or not employee_code:
            return render_template("manual.html", reason_options=REASON_OPTIONS,
                                 error="Employee Name and Code are required.")
        
        if output_format not in OUTPUT_FORMATS:
            return render_template("manual.html", reason_options=REASON_OPTIONS,
                                 error="Invalid output format.")
        
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
        
        # Apply HR rules
        employee.issues = apply_attendance_limits(employee.issues)
        logger.info(f"[MANUAL] HR rules applied: {len(employee.issues)} final rows")
        
        # Generate document
        logger.info("[MANUAL] Word generation started")
        
        job_id = uuid.uuid4().hex
        job_output_dir = app.config["OUTPUT_FOLDER"] / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)
        
        docx_path = job_output_dir / f"{employee_code}_{employee_name}.docx"
        
        create_single_docx(
            employee,
            str(docx_path),
            company_name,
            month,
            department
        )
        
        logger.info(f"[MANUAL] Word document saved: {docx_path}")
        
        # Convert to PDF if requested
        output_file = docx_path
        if output_format == "pdf":
            logger.info("[MANUAL] PDF conversion started")
            pdf_path = convert_to_pdf(str(docx_path))
            if pdf_path:
                output_file = Path(pdf_path)
                logger.info(f"[MANUAL] PDF saved: {output_file}")
            else:
                logger.warning("[MANUAL] PDF conversion failed, returning DOCX instead")
        
        logger.info("[MANUAL] Sending file to user")
        
        return send_file(
            output_file,
            as_attachment=True,
            download_name=f"{employee_code}_{employee_name}.{output_format}"
        )
    
    except Exception as exc:
        logger.error("[MANUAL] EXCEPTION OCCURRED")
        logger.error(traceback.format_exc())
        
        # Clean up on error
        if job_output_dir:
            shutil.rmtree(job_output_dir, ignore_errors=True)
        
        return render_template("manual.html", reason_options=REASON_OPTIONS,
                             error=f"Error generating document: {exc}")


@app.route("/upload-excel", methods=["GET"])
def upload_excel_page():
    """Upload Excel page."""
    ensure_project_folders()
    logger.info("[EXCEL] GET /upload-excel - Rendering upload form")
    return render_template("upload_excel.html")


@app.route("/parse-excel", methods=["POST"])
def parse_excel():
    """Parse Excel file and return data for manual entry."""
    ensure_project_folders()
    
    try:
        logger.info("[EXCEL] POST /parse-excel - Request received")
        
        uploaded_file = request.files.get("attendance_file")
        
        if not uploaded_file or uploaded_file.filename == "":
            return jsonify({"error": "Please upload a file."}), 400
        
        if not allowed_file(uploaded_file.filename):
            return jsonify({"error": "Upload a .xlsx or .xls file."}), 400
        
        job_id = uuid.uuid4().hex
        safe_name = secure_filename(uploaded_file.filename)
        upload_path = app.config["UPLOAD_FOLDER"] / f"{job_id}_{safe_name}"
        
        uploaded_file.save(upload_path)
        logger.info(f"[EXCEL] File saved: {upload_path}")
        
        # Parse Excel
        logger.info("[EXCEL] Starting parsing")
        records, month = parse_attendance_file(str(upload_path))
        logger.info(f"[EXCEL] Parsing complete. Found {len(records)} records. Month: {month}")
        
        if not records:
            return jsonify({"error": "No employee records found in the Excel file."}), 400
        
        # Return first employee's data for manual entry
        first_employee = records[0]
        
        return jsonify({
            "success": True,
            "company_name": "",
            "employee_name": first_employee.name,
            "employee_code": first_employee.code,
            "month": month,
            "attendance_data": [
                {"date": issue.date, "reason": issue.reason}
                for issue in first_employee.issues
            ],
            "total_employees": len(records),
            "message": f"Loaded {len(records)} employees from Excel. First employee displayed below."
        })
    
    except Exception as exc:
        logger.error("[EXCEL] EXCEPTION OCCURRED")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Error parsing file: {exc}"}), 500


@app.route("/upload-image", methods=["GET"])
def upload_image_page():
    """Upload Image page."""
    ensure_project_folders()
    logger.info("[IMAGE] GET /upload-image - Rendering upload form")
    return render_template("upload_image.html")


@app.route("/parse-image", methods=["POST"])
def parse_image():
    """Parse image/PDF and return OCR text for manual entry."""
    ensure_project_folders()
    
    try:
        logger.info("[IMAGE] POST /parse-image - Request received")
        
        uploaded_file = request.files.get("attendance_file")
        
        if not uploaded_file or uploaded_file.filename == "":
            return jsonify({"error": "Please upload a file."}), 400
        
        file_ext = Path(uploaded_file.filename).suffix.lower()
        if file_ext not in {".png", ".jpg", ".jpeg", ".pdf"}:
            return jsonify({"error": "Upload a PNG, JPG, JPEG, or PDF file."}), 400
        
        job_id = uuid.uuid4().hex
        safe_name = secure_filename(uploaded_file.filename)
        upload_path = app.config["UPLOAD_FOLDER"] / f"{job_id}_{safe_name}"
        
        uploaded_file.save(upload_path)
        logger.info(f"[IMAGE] File saved: {upload_path}")
        
        # Extract text via OCR
        logger.info("[IMAGE] Starting OCR extraction")
        text = extract_text_from_image_or_pdf(str(upload_path))
        logger.info(f"[IMAGE] OCR complete. Extracted {len(text)} characters")
        
        if not text.strip():
            return jsonify({"error": "Could not extract text from image. Please try a clearer image."}), 400
        
        # Parse extracted text
        logger.info("[IMAGE] Parsing OCR text")
        records, month = parse_attendance_file(str(upload_path))
        logger.info(f"[IMAGE] Parsing complete. Found {len(records)} records. Month: {month}")
        
        if not records:
            return jsonify({"error": "Could not extract employee records from image. Please try a clearer image."}), 400
        
        # Return first employee's data
        first_employee = records[0]
        
        return jsonify({
            "success": True,
            "company_name": "",
            "employee_name": first_employee.name,
            "employee_code": first_employee.code,
            "month": month,
            "attendance_data": [
                {"date": issue.date, "reason": issue.reason}
                for issue in first_employee.issues
            ],
            "total_employees": len(records),
            "message": f"Extracted {len(records)} employees from image. First employee displayed below."
        })
    
    except Exception as exc:
        logger.error("[IMAGE] EXCEPTION OCCURRED")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Error processing image: {exc}"}), 500


@app.route("/preview", methods=["POST"])
def preview():
    """Preview the document before generation."""
    try:
        logger.info("[PREVIEW] POST /preview - Request received")
        
        # Parse form data
        company_name = request.form.get("company_name", "Company Name").strip() or "Company Name"
        employee_name = request.form.get("employee_name", "").strip()
        employee_code = request.form.get("employee_code", "").strip()
        department = request.form.get("department", "").strip()
        month = request.form.get("month", datetime.now().strftime("%B %Y")).strip()
        
        # Parse attendance rows
        attendance_dates = request.form.getlist("attendance_date[]")
        attendance_reasons = request.form.getlist("attendance_reason[]")
        
        issues = []
        for date_str, reason in zip(attendance_dates, attendance_reasons):
            if date_str and reason:
                issues.append(AttendanceIssue(date=date_str, reason=reason))
        
        # Apply HR rules
        final_issues = apply_attendance_limits(issues)
        
        logger.info(f"[PREVIEW] Preview data: {len(final_issues)} rows after HR rules")
        
        return jsonify({
            "success": True,
            "preview": {
                "company_name": company_name,
                "employee_name": employee_name,
                "employee_code": employee_code,
                "department": department,
                "month": month,
                "date_generated": datetime.now().strftime("%d-%m-%Y"),
                "issues": [
                    {"s_no": idx + 1, "date": issue.date, "reason": issue.reason}
                    for idx, issue in enumerate(final_issues)
                ]
            }
        })
    
    except Exception as exc:
        logger.error("[PREVIEW] EXCEPTION OCCURRED")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Error generating preview: {exc}"}), 500


if __name__ == "__main__":
    ensure_project_folders()
    app.run(debug=True)
