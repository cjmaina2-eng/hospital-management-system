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
        reason = request.form.get('reason')
        other_reason = request.form.get('other_reason')

        if not all([doctor_id, appointment_date, reason]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('appointment.new'))

        if reason == 'Other':
            if not other_reason or not other_reason.strip():
                flash('Please specify the appointment reason.', 'danger')
                return redirect(url_for('appointment.new'))
            reason = other_reason.strip()

        # Parse appointment date
        try:
            appt_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format.', 'danger')
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

        # Check doctor exists
        doctor = Doctor.query.get(doctor_id)
        if not doctor:
            flash('Doctor not found.', 'danger')
            return redirect(url_for('appointment.new'))

        # Create appointment with PENDING status (time to be assigned by doctor)
        appt = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date_requested=appt_date,
            appointment_date=None,  # Will be set when doctor accepts and assigns time
            appointment_time=None,   # Will be set when doctor accepts and assigns time
            reason=reason,
            status='Pending'  # <-- Doctor must accept/reject and assign time
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
    return render_template('appointment/new.html',
                           doctors=doctors,
                           patients=patients,
                           patient=patient,
                           today=today)

@bp.route('/check_availability', methods=['GET'])
@login_required
def check_availability():
    """JSON endpoint to check if a doctor is available on a date."""
    doctor_id = request.args.get('doctor_id')
    date = request.args.get('date')

    if not all([doctor_id, date]):
        return jsonify({'available': False, 'message': 'Missing parameters'}), 400

    try:
        appt_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'available': False, 'message': 'Invalid date format'}), 400

    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'available': False, 'message': 'Doctor not found'}), 404

    # Check if date is today or in the past
    today = datetime.now().date()
    if appt_date < today:
        return jsonify({
            'available': False,
            'message': 'Cannot book appointments in the past.'
        })

    # Check conflicting appointments for this date (only those with assigned times)
    existing = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date_requested == appt_date,
        Appointment.status.in_(['Pending', 'Accepted'])
    ).count()

    return jsonify({
        'available': True,
        'message': f'Dr. {doctor.user.first_name} {doctor.user.last_name} is available on this date!',
        'doctor_name': f"Dr. {doctor.user.first_name} {doctor.user.last_name}",
        'specialization': doctor.specialization,
        'pending_count': existing
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

@bp.route('/<int:id>/accept', methods=['GET', 'POST'])
@login_required
def accept(id):
    """Doctor accepts a pending appointment and assigns a time."""
    appointment = Appointment.query.get_or_404(id)
    
    # Only the assigned doctor can accept
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor or doctor.id != appointment.doctor_id:
        flash('You are not authorized to accept this appointment.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    if appointment.status != 'Pending':
        flash('This appointment is no longer pending.', 'warning')
        return redirect(url_for('dashboard.index'))
    
    # GET: Show form to select time
    if request.method == 'GET':
        return render_template('appointment/accept.html', appointment=appointment)
    
    # POST: Process time selection
    appointment_time = request.form.get('appointment_time')
    
    if not appointment_time:
        flash('Please select a time.', 'danger')
        return render_template('appointment/accept.html', appointment=appointment)
    
    try:
        # Combine date and time
        dt = datetime.strptime(f"{appointment.appointment_date_requested} {appointment_time}", '%Y-%m-%d %H:%M')
    except ValueError:
        flash('Invalid time format.', 'danger')
        return render_template('appointment/accept.html', appointment=appointment)
    
    # Validate working hours
    hour = dt.hour
    if hour < 8 or hour >= 18:
        flash('Please select a time between 8:00 AM and 6:00 PM.', 'danger')
        return render_template('appointment/accept.html', appointment=appointment)
    
    # Check for conflicting appointments at this time
    conflict = Appointment.query.filter(
        Appointment.doctor_id == appointment.doctor_id,
        Appointment.appointment_date == dt,
        Appointment.status.in_(['Accepted']),
        Appointment.id != appointment.id
    ).first()
    if conflict:
        flash('This time slot conflicts with another appointment. Please choose another time.', 'danger')
        return render_template('appointment/accept.html', appointment=appointment)
    
    # Accept and assign time
    appointment.appointment_date = dt
    appointment.appointment_time = appointment_time
    appointment.status = 'Accepted'
    db.session.commit()
    queue_appointment_email(appointment, 'Accepted')
    flash('Appointment accepted and time assigned. The patient has been notified by email.', 'success')
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
