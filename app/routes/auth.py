from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db, mail
from app.models import User, Role, VerificationCode
from werkzeug.security import generate_password_hash
import secrets
from datetime import datetime, timedelta
from flask_mail import Message

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('auth/login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    # Only admin can register new users
    if not current_user.has_role('admin'):
        flash('You do not have permission to register users.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        role_name = request.form.get('role')
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('auth.register'))
        
        # Create user
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=True
        )
        user.set_password(password)
        
        # Assign role
        role = Role.query.filter_by(name=role_name).first()
        if role:
            user.roles.append(role)
        else:
            flash('Invalid role selected.', 'danger')
            return redirect(url_for('auth.register'))
        
        db.session.add(user)
        db.session.commit()
        flash('User created successfully!', 'success')
        return redirect(url_for('auth.login'))
    
    roles = Role.query.all()
    return render_template('auth/register.html', roles=roles)

# --- Login with Code Routes ---

@bp.route('/send-code', methods=['POST'])
def send_code():
    # ... existing code ...
    
    try:
        msg = Message(
            subject="Your Login Code - Kirwara Hospital",
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[email],
            html=f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
                <div style="text-align: center; padding-bottom: 20px; border-bottom: 2px solid #2563eb;">
                    <h2 style="color: #2563eb; margin: 0;">🏥 Kirwara Hospital</h2>
                    <p style="color: #64748b; margin: 5px 0;">Quality Healthcare Services</p>
                </div>
                <div style="padding: 20px 0;">
                    <p>Dear <strong>{user.first_name or 'User'}</strong>,</p>
                    <p>You requested a one-time login code for the Kirwara Hospital Management System.</p>
                    <div style="text-align: center; margin: 30px 0; padding: 20px; background: #f8fafc; border-radius: 8px;">
                        <span style="font-size: 36px; letter-spacing: 8px; font-weight: bold; color: #2563eb;">{code}</span>
                    </div>
                    <p>This code is valid for <strong>10 minutes</strong>. If you did not request this, please ignore this email.</p>
                </div>
                <div style="padding-top: 20px; border-top: 1px solid #e2e8f0; text-align: center; color: #94a3b8; font-size: 12px;">
                    <p>Kirwara Hospital &bull; Quality Healthcare Services</p>
                </div>
            </div>
            """
        )
        mail.send(msg)
        # ... rest of code ...

@bp.route('/verify-code', methods=['POST'])
def verify_code():
    from flask import session
    email = session.get('login_code_email')
    if not email:
        flash('Please request a code first.', 'danger')
        return redirect(url_for('auth.login'))

    code = request.form.get('code')
    if not code:
        flash('Please enter the code.', 'danger')
        return redirect(url_for('auth.login'))

    if VerificationCode.verify(email, code):
        user = User.query.filter_by(email=email).first()
        if user:
            login_user(user)
            flash('Logged in with code successfully!', 'success')
            session.pop('login_code_email', None)
            return redirect(url_for('dashboard.index'))
        else:
            flash('User not found.', 'danger')
    else:
        flash('Invalid or expired code.', 'danger')

    return redirect(url_for('auth.login'))

# --- Forgot Password Routes ---

import threading

def send_reset_email_async(app, msg):
    """Send email in a separate thread to avoid blocking."""
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            app.logger.error(f"Async email error: {e}")

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    # ... existing code ...
    
    try:
        msg = Message(
            subject="Password Reset - Kirwara Hospital Management System",
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[email],
            html=f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
                <div style="text-align: center; padding-bottom: 20px; border-bottom: 2px solid #2563eb;">
                    <h2 style="color: #2563eb; margin: 0;">🏥 Kirwara Hospital</h2>
                    <p style="color: #64748b; margin: 5px 0;">Quality Healthcare Services</p>
                </div>
                <div style="padding: 20px 0;">
                    <h3 style="color: #0f172a;">Reset Your Password</h3>
                    <p>You requested to reset your password for the Kirwara Hospital Management System.</p>
                    <p>Click the button below to reset your password (valid for 1 hour):</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_url}" style="display: inline-block; padding: 12px 32px; background: #2563eb; color: white; text-decoration: none; border-radius: 8px; font-weight: bold;">
                            Reset Password
                        </a>
                    </div>
                    <p style="color: #64748b; font-size: 14px;">If you did not request this, please ignore this email.</p>
                </div>
                <div style="padding-top: 20px; border-top: 1px solid #e2e8f0; text-align: center; color: #94a3b8; font-size: 12px;">
                    <p>Kirwara Hospital &bull; Quality Healthcare Services</p>
                    <p>© 2026 All Rights Reserved</p>
                </div>
            </div>
            """
        )
        mail.send(msg)
        # ... rest of code ...

@bp.route('/send-code', methods=['POST'])
def send_code():
    from app import mail
    from flask_mail import Message

    email = request.form.get('email')
    if not email:
        flash('Email is required.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('No account found with that email.', 'danger')
        return redirect(url_for('auth.login'))

    code = VerificationCode.create_for_email(email)

    # --- TRY TO SEND EMAIL ---
    email_sent = False
    try:
        msg = Message(
            subject="Your Login Code - MyHHub",
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[email],
            html=f"""
            <p>Dear <strong>{user.first_name or 'User'}</strong>,</p>
            <p>Your verification code is: <strong style="font-size: 24px; color: #2563eb;">{code}</strong></p>
            <p>This code is valid for <strong>10 minutes</strong>.</p>
            <p>Thank you,<br>MyHHub Team</p>
            """
        )
        mail.send(msg)
        email_sent = True
        flash('A verification code has been sent to your email.', 'success')
    except Exception as e:
        current_app.logger.error(f"Email send failed: {e}")
        flash(f'Could not send email. Your code is: {code}', 'warning')

    # --- FALLBACK: Show code in flash ---
    if not email_sent:
        flash(f'Your verification code is: {code}', 'info')

    session['login_code_email'] = email
    return redirect(url_for('auth.login'))

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    # Find user with valid token
    user = User.query.filter_by(reset_token=token).first()
    if not user:
        flash('Invalid or expired reset token.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    if user.reset_token_expires and user.reset_token_expires < datetime.utcnow():
        flash('Reset link has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
        
        # Update password
        user.set_password(password)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()
        
        flash('Your password has been reset successfully. Please login.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', token=token)