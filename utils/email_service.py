from flask_mail import Mail, Message
import logging

logger = logging.getLogger(__name__)
mail = Mail()


def send_forms_email(recipient_email, subject, docx_path=None, pdf_path=None):
    """
    Send generated forms to email.
    
    Args:
        recipient_email: Email address to send to
        subject: Email subject
        docx_path: Path to Word document
        pdf_path: Path to PDF document
    
    Returns:
        bool: True if sent successfully
    """
    try:
        msg = Message(
            subject=subject,
            recipients=[recipient_email]
        )
        
        msg.body = """
Hello,

Your attendance correction form has been generated and is attached.

Best regards,
HR Attendance Portal
        """
        
        # Attach files
        if docx_path:
            with open(docx_path, 'rb') as f:
                msg.attach(
                    filename=docx_path.split('/')[-1],
                    content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    data=f.read()
                )
        
        if pdf_path:
            with open(pdf_path, 'rb') as f:
                msg.attach(
                    filename=pdf_path.split('/')[-1],
                    content_type='application/pdf',
                    data=f.read()
                )
        
        mail.send(msg)
        logger.info(f"Email sent successfully to {recipient_email}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
        return False


def send_batch_notification(recipient_email, job_summary):
    """
    Send batch processing notification.
    
    Args:
        recipient_email: Email address
        job_summary: Dict with processing details
    
    Returns:
        bool: True if sent successfully
    """
    try:
        msg = Message(
            subject=f"Batch Processing Complete: {job_summary.get('employee_count', 0)} Forms Generated",
            recipients=[recipient_email]
        )
        
        msg.body = f"""
Hello,

Your batch processing job has completed successfully.

Summary:
- Total Employees: {job_summary.get('employee_count', 0)}
- Status: {job_summary.get('status', 'completed')}
- Output Format: {job_summary.get('output_format', 'Word')}
- Processing Time: {job_summary.get('processing_time', 'N/A')}

Your files are ready for download.

Best regards,
HR Attendance Portal
        """
        
        mail.send(msg)
        logger.info(f"Batch notification sent to {recipient_email}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to send batch notification: {str(e)}")
        return False
