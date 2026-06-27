from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from models import db, User

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login."""
    if request.method == 'GET':
        return render_template('auth/login.html')
    
    try:
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        if not username or not password:
            flash('Username and password required', 'error')
            return redirect(url_for('auth.login'))
        
        # Find user
        user = User.query.filter_by(username=username).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            logger.warning(f"Failed login attempt for username: {username}")
            flash('Invalid username or password', 'error')
            return redirect(url_for('auth.login'))
        
        # Create session
        session['user_id'] = user.id
        session['username'] = user.username
        session['company_name'] = user.company_name
        session.permanent = bool(remember)
        
        logger.info(f"User logged in: {username}")
        flash(f'Welcome back, {username}!', 'success')
        
        return redirect(url_for('index'))
    
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        flash('An error occurred during login', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration."""
    if request.method == 'GET':
        return render_template('auth/register.html')
    
    try:
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        company_name = request.form.get('company_name', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not all([username, email, company_name, password]):
            flash('All fields required', 'error')
            return redirect(url_for('auth.register'))
        
        if len(username) < 3:
            flash('Username must be at least 3 characters', 'error')
            return redirect(url_for('auth.register'))
        
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'error')
            return redirect(url_for('auth.register'))
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('auth.register'))
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('auth.register'))
        
        # Create user
        user = User(
            username=username,
            email=email,
            company_name=company_name,
            password_hash=generate_password_hash(password)
        )
        
        db.session.add(user)
        db.session.commit()
        
        logger.info(f"New user registered: {username}")
        flash('Account created successfully! Please login.', 'success')
        
        return redirect(url_for('auth.login'))
    
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        flash('An error occurred during registration', 'error')
        return redirect(url_for('auth.register'))


@auth_bp.route('/logout')
def logout():
    """User logout."""
    username = session.get('username', 'User')
    session.clear()
    logger.info(f"User logged out: {username}")
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))
