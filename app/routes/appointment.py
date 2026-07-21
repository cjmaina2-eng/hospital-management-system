import threading

from flask import Blueprint, current_app, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from flask_mail import Message
from app import db
from app import mail
from app.models import Appointment, Patient, Doctor
from datetime import datetime

bp = Blueprint('appointment', __name__, url_prefix='/appointments')


def send_email_async(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            app.logger.error(f"Appointment email error: {e}")


def queue_appointment_email(appointment, decision):
    patient_user = appointment.patient.user
    doctor_user = appointment.doctor.user
    status_text = decision.lower()
    appointment_url = url_for('appointment.view', id=appointment.id, _external=True)
    msg = Message(
        subject=f"Appointment {decision} - Kirwara Hospital",
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[patient_user.email],
        html=f"""
        <p>Dear <strong>{patient_user.first_name}</strong>,</p>
        <p>Your appointment with <strong>Dr. {doctor_user.first_name} {doctor_user.last_name}</strong>
        on <strong>{appointment.appointment_date.strftime('%B %d, %Y at %H:%M')}</strong>
        has been <strong>{status_text}</strong>.</p>
        <p><strong>Reason:</strong> {appointment.reason}</p>
        <p><a href="{appointment_url}">View appointment details</a></p>
        <p>Thank you,<br>Kirwara Hospital Team</p>
        """
    )
    app = current_app._get_current_object()
    thread = threading.Thread(target=send_email_async, args=(app, msg), daemon=True)
    thread.start()

@bp.route('/')
@login_required
def index():
    """List appointments based on role."""
    if current_user.has_role('patient'):
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        if not patient:
            flash('You are not registered as a patient.', 'warning')
            return redirect(url_for('dashboard.index'))
        appointments = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.appointment_date.desc()).all()
    elif current_user.has_role('doctor'):
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
        if not doctor:
            flash('You are not registered as a doctor.', 'warning')
            return redirect(url_for('dashboard.index'))
        appointments = Appointment.query.filter_by(doctor_id=doctor.id).order_by(Appointment.appointment_date.desc()).all()
    else:
        # Admin / Receptionist: see all
        appointments = Appointment.query.order_by(Appointment.appointment_date.desc()).all()

    return render_template('appointment/index.html', appointments=appointments)

@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Book a new appointment."""
    # Check permission
    if not (current_user.has_role('patient') or current_user.has_role('admin') or current_user.has_role('receptionist')):
        flash('You do not have permission to book appointments.', 'danger')
        return redirect(url_for('appointment.index'))

    # Get patient if current user is a patient
    patient = None
    if current_user.has_role('patient'):
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        if not patient:
            flash('Patient profile not found. Please contact admin.', 'danger')
            return redirect(url_for('appointment.index'))

    # POST: handle form submission
    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id')
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        reason = request.form.get('reason')

        if not all([doctor_id, appointment_date, appointment_time, reason]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('appointment.new'))

        # Combine date and time
        try:
            dt = datetime.strptime(f"{appointment_date} {appointment_time}", '%Y-%m-%d %H:%M')
        except ValueError:
            flash('Invalid date or time format.', 'danger')
            return redirect(url_for('appointment.new'))

        # If admin/receptionist, they must select a patient
        if not patient:
            patient_id = request.form.get('patient_id')
            if not patient_id:
                flash('Please select a patient.', 'danger')
                return redirect(url_for('appointment.new'))
            patient = Patient.query.get(patient_id)
            if not patient:
                flash('Patient not found.', 'danger')
                return redirect(url_for('appointment.new'))

        # Check doctor exists and is free
        doctor = Doctor.query.get(doctor_id)
        if not doctor:
            flash('Doctor not found.', 'danger')
            return redirect(url_for('appointment.new'))

        if doctor.status != 'free':
            flash(f'Dr. {doctor.user.first_name} {doctor.user.last_name} is not available at the moment (status: {doctor.status}).', 'danger')
            return redirect(url_for('appointment.new'))

        # Check for conflicting appointments
        conflict = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == dt,
            Appointment.status.in_(['Pending', 'Accepted', 'Scheduled'])
        ).first()
        if conflict:
            flash('This time slot is already booked. Please choose another.', 'danger')
            return redirect(url_for('appointment.new'))

        # Create appointment with PENDING status
        appt = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date=dt,
            reason=reason,
            status='Pending'  # <-- Doctor must accept/reject
        )
        db.session.add(appt)
        db.session.commit()

        flash('Appointment booked successfully! Waiting for doctor confirmation.', 'success')
        return redirect(url_for('appointment.index'))

    # GET: prepare form data
    doctors = Doctor.query.all()  # All doctors, regardless of status
    patients = None
    if current_user.has_role('admin') or current_user.has_role('receptionist'):
        patients = Patient.query.all()

    today = datetime.now().strftime('%Y-%m-%d')
    now_time = datetime.now().strftime('%H:%M')
    return render_template('appointment/new.html',
                           doctors=doctors,
                           patients=patients,
                           patient=patient,
                           today=today,
                           now_time=now_time)

@bp.route('/check_availability', methods=['GET'])
@login_required
def check_availability():
    """JSON endpoint to check if a doctor is available."""
    doctor_id = request.args.get('doctor_id')
    date = request.args.get('date')
    time = request.args.get('time')

    if not all([doctor_id, date, time]):
        return jsonify({'available': False, 'message': 'Missing parameters'}), 400

    try:
        dt = datetime.strptime(f"{date} {time}", '%Y-%m-%d %H:%M')
    except ValueError:
        return jsonify({'available': False, 'message': 'Invalid date/time format'}), 400

    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'available': False, 'message': 'Doctor not found'}), 404

    # Check status
    if doctor.status != 'free':
        status_map = {
            'in_session': 'currently in a consultation',
            'on_leave': 'on leave',
            'lunch_break': 'on lunch break',
            'in_surgery': 'in surgery'
        }
        reason = status_map.get(doctor.status, 'unavailable')
        return jsonify({
            'available': False,
            'message': f'Dr. {doctor.user.first_name} {doctor.user.last_name} is {reason}.'
        })

    # Check conflicting appointments (including pending ones)
    existing = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == dt,
        Appointment.status.in_(['Pending', 'Accepted', 'Scheduled'])
    ).first()
    if existing:
        return jsonify({
            'available': False,
            'message': f'Dr. {doctor.user.first_name} {doctor.user.last_name} is already booked at this time.'
        })

    # Working hours
    hour = dt.hour
    if hour < 8 or hour >= 18:
        return jsonify({
            'available': False,
            'message': 'Please select a time between 8:00 AM and 6:00 PM.'
        })

    return jsonify({
        'available': True,
        'message': f'Dr. {doctor.user.first_name} {doctor.user.last_name} is available!',
        'doctor_name': f"Dr. {doctor.user.first_name} {doctor.user.last_name}",
        'specialization': doctor.specialization
    })

@bp.route('/<int:id>')
@login_required
def view(id):
    appointment = Appointment.query.get_or_404(id)
    # Authorisation: patient themselves, their doctor, admin, receptionist
    if current_user.has_role('patient'):
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        if not patient or patient.id != appointment.patient_id:
            flash('Access denied.', 'danger')
            return redirect(url_for('appointment.index'))
    elif current_user.has_role('doctor'):
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
        if doctor and doctor.id != appointment.doctor_id:
            flash('Access denied.', 'danger')
            return redirect(url_for('appointment.index'))
    elif current_user.has_role('admin') or current_user.has_role('receptionist'):
        pass  # allowed
    else:
        flash('Access denied.', 'danger')
        return redirect(url_for('appointment.index'))

    return render_template('appointment/view.html', appointment=appointment)

@bp.route('/<int:id>/accept', methods=['POST'])
@login_required
def accept(id):
    """Doctor accepts a pending appointment."""
    appointment = Appointment.query.get_or_404(id)
    
    # Only the assigned doctor can accept
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor or doctor.id != appointment.doctor_id:
        flash('You are not authorized to accept this appointment.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    if appointment.status != 'Pending':
        flash('This appointment is no longer pending.', 'warning')
        return redirect(url_for('dashboard.index'))
    
    appointment.status = 'Accepted'
    db.session.commit()
    queue_appointment_email(appointment, 'Accepted')
    flash('Appointment accepted. The patient has been notified by email.', 'success')
    return redirect(request.referrer or url_for('dashboard.index'))

@bp.route('/<int:id>/reject', methods=['POST'])
@login_required
def reject(id):
    """Doctor rejects a pending appointment."""
    appointment = Appointment.query.get_or_404(id)
    
    # Only the assigned doctor can reject
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor or doctor.id != appointment.doctor_id:
        flash('You are not authorized to reject this appointment.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    if appointment.status != 'Pending':
        flash('This appointment is no longer pending.', 'warning')
        return redirect(url_for('dashboard.index'))
    
    appointment.status = 'Rejected'
    db.session.commit()
    queue_appointment_email(appointment, 'Rejected')
    flash('Appointment rejected. The patient has been notified by email.', 'info')
    return redirect(request.referrer or url_for('dashboard.index'))

@bp.route('/<int:id>/cancel', methods=['POST'])
@login_required
def cancel(id):
    """Cancel an appointment (patient, admin, receptionist)."""
    appointment = Appointment.query.get_or_404(id)
    
    # Permissions: patient, admin, receptionist can cancel
    if current_user.has_role('patient'):
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        if not patient or patient.id != appointment.patient_id:
            flash('You cannot cancel this appointment.', 'danger')
            return redirect(url_for('appointment.index'))
    elif not (current_user.has_role('admin') or current_user.has_role('receptionist')):
        flash('Permission denied.', 'danger')
        return redirect(url_for('appointment.index'))

    appointment.status = 'Cancelled'
    db.session.commit()
    flash('Appointment cancelled.', 'success')
    return redirect(url_for('appointment.index'))
