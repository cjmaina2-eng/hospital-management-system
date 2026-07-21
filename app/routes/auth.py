from datetime import datetime, timedelta
import secrets
import threading

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_mail import Message

from app import db, mail
from app.models import Patient, Role, User, VerificationCode


bp = Blueprint('auth', __name__, url_prefix='/auth')


def send_email_async(app, msg):
    """Send mail outside the request thread when possible."""
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            app.logger.error(f"Async email error: {e}")


def queue_email(msg):
    app = current_app._get_current_object()
    thread = threading.Thread(target=send_email_async, args=(app, msg), daemon=True)
    thread.start()


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
    if not current_user.has_role('admin'):
        flash('You do not have permission to register users.', 'danger')
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        role_name = request.form.get('role')

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('auth.register'))

        role = Role.query.filter_by(name=role_name).first()
        if not role:
            flash('Invalid role selected.', 'danger')
            return redirect(url_for('auth.register'))

        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=True
        )
        user.set_password(password)
        user.roles.append(role)

        db.session.add(user)
        db.session.commit()
        flash('User created successfully!', 'success')
        return redirect(url_for('auth.login'))

    roles = Role.query.all()
    return render_template('auth/register.html', roles=roles)


@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        national_id = request.form.get('national_id')
        date_of_birth = request.form.get('date_of_birth')
        gender = request.form.get('gender')
        phone = request.form.get('phone')

        if not all([email, first_name, last_name, password, confirm_password, national_id, date_of_birth, gender, phone]):
            flash('Please complete all required fields.', 'danger')
            return redirect(url_for('auth.signup'))

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.signup'))

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return redirect(url_for('auth.signup'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('auth.signup'))

        if Patient.query.filter_by(national_id=national_id).first():
            flash('A patient with this National ID already exists.', 'danger')
            return redirect(url_for('auth.signup'))

        patient_role = Role.query.filter_by(name='patient').first()
        if not patient_role:
            flash('Patient role not found. Please contact the administrator.', 'danger')
            return redirect(url_for('auth.signup'))

        try:
            dob = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
        except ValueError:
            flash('Please enter a valid date of birth.', 'danger')
            return redirect(url_for('auth.signup'))

        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=True
        )
        user.set_password(password)
        user.roles.append(patient_role)
        db.session.add(user)
        db.session.flush()

        patient = Patient(
            user_id=user.id,
            national_id=national_id,
            date_of_birth=dob,
            gender=gender,
            phone=phone,
            address=request.form.get('address'),
            city=request.form.get('city'),
            state=request.form.get('state'),
            postal_code=request.form.get('postal_code'),
            blood_type=request.form.get('blood_type'),
            allergies=request.form.get('allergies'),
            emergency_contact_name=request.form.get('emergency_contact_name'),
            emergency_contact_phone=request.form.get('emergency_contact_phone'),
            emergency_contact_relationship=request.form.get('emergency_contact_relationship')
        )
        db.session.add(patient)
        db.session.commit()

        flash('Your patient account has been created. Please sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/signup.html')


@bp.route('/send-code', methods=['POST'])
def send_code():
    email = request.form.get('email')
    if not email:
        flash('Email is required.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('No account found with that email.', 'danger')
        return redirect(url_for('auth.login'))

    code = VerificationCode.create_for_email(email)
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

    try:
        mail.send(msg)
        flash('A verification code has been sent to your email.', 'success')
    except Exception as e:
        current_app.logger.error(f"Email send failed: {e}")
        flash(f'Could not send email. Your verification code is: {code}', 'warning')

    session['login_code_email'] = email
    return redirect(url_for('auth.login'))


@bp.route('/verify-code', methods=['POST'])
def verify_code():
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
        if user and user.is_active:
            login_user(user)
            session.pop('login_code_email', None)
            flash('Logged in with code successfully!', 'success')
            return redirect(url_for('dashboard.index'))

        flash('User not found or inactive.', 'danger')
    else:
        flash('Invalid or expired code.', 'danger')

    return redirect(url_for('auth.login'))


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            user.reset_token = secrets.token_urlsafe(32)
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()

            reset_url = url_for('auth.reset_password', token=user.reset_token, _external=True)
            msg = Message(
                subject="Password Reset - MyHHub",
                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=[user.email],
                html=f"""
                <p>Dear <strong>{user.first_name or 'User'}</strong>,</p>
                <p>You requested to reset your password.</p>
                <p><a href="{reset_url}">Reset your password</a></p>
                <p>This link is valid for 1 hour. If you did not request this, please ignore this email.</p>
                """
            )

            try:
                queue_email(msg)
            except Exception as e:
                current_app.logger.error(f"Password reset email failed: {e}")

        flash('If that email exists, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

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

        user.set_password(password)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()

        flash('Your password has been reset successfully. Please login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)
