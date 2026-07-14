from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_mail import Message

from app import db, mail
from app.models import Role, User, VerificationCode

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

        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        user.set_password(password)

        role = Role.query.filter_by(name=role_name).first()
        if not role:
            flash('Invalid role selected.', 'danger')
            return redirect(url_for('auth.register'))

        user.roles.append(role)
        db.session.add(user)
        db.session.commit()
        flash('User created successfully!', 'success')
        return redirect(url_for('auth.login'))

    roles = Role.query.all()
    return render_template('auth/register.html', roles=roles)


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
    session['login_code_email'] = email

    try:
        sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME')
        if not sender:
            raise RuntimeError('MAIL_DEFAULT_SENDER or MAIL_USERNAME is not configured')

        msg = Message(
            subject='Your Login Code - MyHHub',
            sender=sender,
            recipients=[email],
            body=(
                f"Dear {user.first_name or 'User'},\n\n"
                "You requested a one-time login code for MyHHub Hospital Management System.\n\n"
                f"Your verification code is: {code}\n\n"
                "This code is valid for 10 minutes. If you did not request this, please ignore this email.\n\n"
                "Thank you,\nMyHHub Team"
            ),
            html=(
                f"<p>Dear <strong>{user.first_name or 'User'}</strong>,</p>"
                "<p>You requested a one-time login code for <strong>MyHHub</strong> Hospital Management System.</p>"
                f'<h2 style="color: #2563eb; font-size: 28px; letter-spacing: 2px;">{code}</h2>'
                "<p>This code is valid for <strong>10 minutes</strong>. If you did not request this, please ignore this email.</p>"
                "<p>Thank you,<br>MyHHub Team</p>"
            ),
        )
        mail.send(msg)
        flash('A verification code has been sent to your email.', 'success')
    except Exception as exc:
        current_app.logger.error('Email send failed: %s', exc)
        flash(f'Email send failed. Your code is: {code} (demo mode)', 'warning')

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
        return redirect(url_for('auth.login'))

    flash('Invalid or expired code.', 'danger')
    return redirect(url_for('auth.login'))
