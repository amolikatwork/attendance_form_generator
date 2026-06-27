import os
import logging
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, send_file, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
from flask_mail import Mail
from flask_apscheduler import APScheduler

from config import config
from models import db, User, Job, EmailLog
from utils.attendance_parser import parse_attendance_file, EmployeeRecord, AttendanceIssue
from utils.document_generator import build_employee_documents, create_single_docx
from utils.email_service import send_forms_email, send_batch_notification, mail
from utils.scheduler import start_scheduler, stop_scheduler
from utils.decorators import login_required
from routes.auth import auth_bp
import uuid
import shutil
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app initialization
app = Flask(__name__)
app.config.from_object(config[os.environ.get('FLASK_ENV', 'development')])

# Initialize extensions
db.init_app(app)
mail.init_app(app)

# Initialize scheduler
scheduler = APScheduler()
scheduler.init_app(app)

# Register blueprints
app.register_blueprint(auth_bp)

# Constants
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
    Path(app.config["UPLOAD_FOLDER"]).mkdir(exist_ok=True)
    Path(app.config["OUTPUT_FOLDER"]).mkdir(exist_ok=True)
    Path("static").mkdir(exist_ok=True)
    Path("templates/auth").mkdir(exist_ok=True)


def allowed_file(filename):
    """Validate uploads by extension before saving them."""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@app.before_request
def check_session_timeout():
    """Check if user session has expired."""
    session.permanent = True
    app.permanent_session_lifetime = app.config['PERMANENT_SESSION_LIFETIME']


@app.route("/", methods=["GET"])
def index():
    """Homepage with navigation to Manual Entry, Upload Excel, and Upload Image."""
    ensure_project_folders()
    
    # Check if user is logged in
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    return render_template("index.html", username=session.get('username'))


@app.route("/manual", methods=["GET", "POST"])
@login_required
def manual_entry():
    """Manual entry page for creating attendance correction forms."""
    ensure_project_folders()
    
    if request.method == "GET":
        logger.info(f"[MANUAL] GET request from user {session.get('username')}")
        return render_template("manual.html", reason_options=REASON_OPTIONS)
    
    # POST request: Generate Word document from manual entry
    try:
        logger.info("[MANUAL] Request received")
        
        # Parse form data
        company_name = request.form.get("company_name", session.get('company_name')).strip() or "Company Name"
        employee_name = request.form.get("employee_name", "").strip()
        employee_code = request.form.get("employee_code", "").strip()
        department = request.form.get("department", "").strip()
        month = request.form.get("month", datetime.now().strftime("%B %Y")).strip()
        send_email = request.form.get("send_email", False) == "on"
        email_recipient = request.form.get("email_recipient", "").strip()
        
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
        job_output_dir = Path(app.config["OUTPUT_FOLDER"]) / job_id
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
        
        # Log job in database
        job = Job(
            job_id=job_id,
            user_id=session.get('user_id'),
            job_type='manual',
            output_format='docx',
            company_name=company_name,
            status='completed',
            employee_count=1,
            output_file=str(docx_path),
            completed_at=datetime.utcnow()
        )
        db.session.add(job)
        db.session.commit()
        
        # Send email if requested
        if send_email and email_recipient:
            email_log = EmailLog(
                user_id=session.get('user_id'),
                job_id=job.id,
                recipient_email=email_recipient
            )
            
            if send_forms_email(email_recipient, f"Attendance Correction Form - {employee_name}", str(docx_path)):
                email_log.status = 'sent'
                email_log.sent_at = datetime.utcnow()
                logger.info(f"[MANUAL] Email sent to {email_recipient}")
            else:
                email_log.status = 'failed'
                logger.error(f"[MANUAL] Failed to send email to {email_recipient}")
            
            db.session.add(email_log)
            db.session.commit()
        
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


@app.route("/upload-excel", methods=["GET", "POST"])
@login_required
def upload_excel():
    """Upload Excel file and generate attendance forms."""
    ensure_project_folders()
    
    if request.method == "GET":
        logger.info(f"[EXCEL] GET request from user {session.get('username')}")
        return render_template("upload_excel.html")
    
    # POST request: Process Excel file
    try:
        logger.info("[EXCEL] Request received")
        
        uploaded_file = request.files.get("attendance_file")
        output_format = request.form.get("output_format", "docx").lower()
        company_name = request.form.get("company_name", session.get('company_name')).strip() or "Company Name"
        send_email = request.form.get("send_email", False) == "on"
        email_recipient = request.form.get("email_recipient", "").strip()

        logger.info(f"[EXCEL] Form data parsed: company_name={company_name}, output_format={output_format}")

        if not uploaded_file or uploaded_file.filename == "":
            return render_template("upload_excel.html", error="Please upload an attendance file.")

        if not allowed_file(uploaded_file.filename):
            return render_template(
                "upload_excel.html",
                error="Upload a .xlsx or .xls file.",
            )

        if output_format not in OUTPUT_FORMATS:
            return render_template("upload_excel.html", error="Choose a valid output format.")

        job_id = uuid.uuid4().hex
        safe_name = secure_filename(uploaded_file.filename)
        upload_path = Path(app.config["UPLOAD_FOLDER"]) / f"{job_id}_{safe_name}"
        job_output_dir = Path(app.config["OUTPUT_FOLDER"]) / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)

        uploaded_file.save(upload_path)
        logger.info(f"[EXCEL] File saved: {upload_path}")

        logger.info("[EXCEL] Starting parsing")
        records, month = parse_attendance_file(str(upload_path))
        logger.info(f"[EXCEL] Parsing complete. Found {len(records)} records. Month: {month}")
        
        if not records:
            raise ValueError("No employee attendance records were found.")

        logger.info("[EXCEL] Word generation started")
        zip_path = build_employee_documents(
            records=records,
            output_dir=job_output_dir,
            output_format=output_format,
            company_name=company_name,
            month=month,
        )
        logger.info(f"[EXCEL] Word saved successfully")
        
        # Log job in database
        job = Job(
            job_id=job_id,
            user_id=session.get('user_id'),
            job_type='excel',
            input_file=safe_name,
            output_format=output_format,
            company_name=company_name,
            status='completed',
            employee_count=len(records),
            output_file=zip_path,
            completed_at=datetime.utcnow()
        )
        db.session.add(job)
        db.session.commit()
        
        # Send notification email if requested
        if send_email and email_recipient:
            send_batch_notification(email_recipient, {
                'employee_count': len(records),
                'status': 'completed',
                'output_format': output_format
            })
        
        logger.info(f"[EXCEL] Returning file")

        return send_file(zip_path, as_attachment=True, download_name="attendance_forms.zip")

    except Exception as exc:
        logger.error(f"[EXCEL] EXCEPTION OCCURRED")
        logger.error(traceback.format_exc())
        shutil.rmtree(job_output_dir, ignore_errors=True)
        return render_template("upload_excel.html", error=f"Could not generate forms: {exc}")


@app.route("/upload-image", methods=["GET", "POST"])
@login_required
def upload_image():
    """Upload image/PDF file and generate attendance forms."""
    ensure_project_folders()
    
    if request.method == "GET":
        logger.info(f"[IMAGE] GET request from user {session.get('username')}")
        return render_template("upload_image.html")
    
    # POST request: Process image/PDF file
    try:
        logger.info("[IMAGE] Request received")
        
        uploaded_file = request.files.get("attendance_file")
        output_format = request.form.get("output_format", "docx").lower()
        company_name = request.form.get("company_name", session.get('company_name')).strip() or "Company Name"
        send_email = request.form.get("send_email", False) == "on"
        email_recipient = request.form.get("email_recipient", "").strip()

        logger.info(f"[IMAGE] Form data parsed: company_name={company_name}, output_format={output_format}")

        if not uploaded_file or uploaded_file.filename == "":
            return render_template("upload_image.html", error="Please upload a file.")

        file_ext = Path(uploaded_file.filename).suffix.lower()
        if file_ext not in {".png", ".jpg", ".jpeg", ".pdf"}:
            return render_template(
                "upload_image.html",
                error="Upload a PNG, JPG, JPEG, or PDF file.",
            )

        if output_format not in OUTPUT_FORMATS:
            return render_template("upload_image.html", error="Choose a valid output format.")

        job_id = uuid.uuid4().hex
        safe_name = secure_filename(uploaded_file.filename)
        upload_path = Path(app.config["UPLOAD_FOLDER"]) / f"{job_id}_{safe_name}"
        job_output_dir = Path(app.config["OUTPUT_FOLDER"]) / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)

        uploaded_file.save(upload_path)
        logger.info(f"[IMAGE] File saved: {upload_path}")

        logger.info("[IMAGE] Starting OCR parsing")
        records, month = parse_attendance_file(str(upload_path))
        logger.info(f"[IMAGE] Parsing complete. Found {len(records)} records. Month: {month}")
        
        if not records:
            raise ValueError("No employee attendance records were found. Please check the image quality.")

        logger.info("[IMAGE] Word generation started")
        zip_path = build_employee_documents(
            records=records,
            output_dir=job_output_dir,
            output_format=output_format,
            company_name=company_name,
            month=month,
        )
        logger.info(f"[IMAGE] Word saved successfully")
        
        # Log job in database
        job = Job(
            job_id=job_id,
            user_id=session.get('user_id'),
            job_type='image',
            input_file=safe_name,
            output_format=output_format,
            company_name=company_name,
            status='completed',
            employee_count=len(records),
            output_file=zip_path,
            completed_at=datetime.utcnow()
        )
        db.session.add(job)
        db.session.commit()
        
        # Send notification email if requested
        if send_email and email_recipient:
            send_batch_notification(email_recipient, {
                'employee_count': len(records),
                'status': 'completed',
                'output_format': output_format
            })
        
        logger.info(f"[IMAGE] Returning file")

        return send_file(zip_path, as_attachment=True, download_name="attendance_forms.zip")

    except Exception as exc:
        logger.error(f"[IMAGE] EXCEPTION OCCURRED")
        logger.error(traceback.format_exc())
        shutil.rmtree(job_output_dir, ignore_errors=True)
        return render_template("upload_image.html", error=f"Could not process file: {exc}")


@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard showing job history."""
    user_id = session.get('user_id')
    jobs = Job.query.filter_by(user_id=user_id).order_by(Job.created_at.desc()).limit(20).all()
    
    return render_template('dashboard.html', jobs=jobs)


@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors."""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    db.session.rollback()
    logger.error(f"Internal error: {error}")
    return render_template('500.html'), 500


if __name__ == "__main__":
    with app.app_context():
        ensure_project_folders()
        db.create_all()
        start_scheduler()
    
    app.run(debug=app.config['DEBUG'])
