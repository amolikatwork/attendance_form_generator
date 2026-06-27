from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    """User account model."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    company_name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    jobs = db.relationship('Job', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.username}>'


class Job(db.Model):
    """Processing job record."""
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(32), unique=True, nullable=False, index=True)  # UUID hex
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Job details
    job_type = db.Column(db.String(20), nullable=False)  # 'manual', 'excel', 'image'
    input_file = db.Column(db.String(255), nullable=True)  # filename if uploaded
    output_format = db.Column(db.String(10), nullable=False)  # 'docx', 'pdf'
    company_name = db.Column(db.String(120), nullable=False)
    
    # Status
    status = db.Column(db.String(20), default='processing')  # 'processing', 'completed', 'failed'
    error_message = db.Column(db.Text, nullable=True)
    
    # Results
    employee_count = db.Column(db.Integer, default=0)
    output_file = db.Column(db.String(255), nullable=True)  # zip or docx path
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<Job {self.job_id} ({self.status})>'
    
    def to_dict(self):
        return {
            'job_id': self.job_id,
            'job_type': self.job_type,
            'status': self.status,
            'employee_count': self.employee_count,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class EmailLog(db.Model):
    """Email sending log."""
    __tablename__ = 'email_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    
    recipient_email = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'sent', 'failed'
    error_message = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime, nullable=True)
    
    job = db.relationship('Job', backref='email_logs')
    
    def __repr__(self):
        return f'<EmailLog {self.recipient_email} ({self.status})>'
