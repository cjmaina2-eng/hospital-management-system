from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Appointment, Patient, Doctor
from datetime import datetime

bp = Blueprint('appointment', __name__, url_prefix='/appointments')

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
            Appointment.status != 'Cancelled'
        ).first()
        if conflict:
            flash('This time slot is already booked. Please choose another.', 'danger')
            return redirect(url_for('appointment.new'))

        # Create appointment
        appt = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date=dt,
            reason=reason,
            status='Scheduled'
        )
        db.session.add(appt)
        db.session.commit()

        flash('Appointment booked successfully!', 'success')
        return redirect(url_for('appointment.index'))

    # GET: prepare form data
    doctors = Doctor.query.all()  # <-- All doctors, regardless of status
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

    # Check conflicting appointments
    existing = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == dt,
        Appointment.status != 'Cancelled'
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
            # optionally allow any doctor to view? We'll restrict to the assigned doctor.
            flash('Access denied.', 'danger')
            return redirect(url_for('appointment.index'))
    elif current_user.has_role('admin') or current_user.has_role('receptionist'):
        pass  # allowed
    else:
        flash('Access denied.', 'danger')
        return redirect(url_for('appointment.index'))

    return render_template('appointment/view.html', appointment=appointment)

@bp.route('/<int:id>/cancel', methods=['POST'])
@login_required
def cancel(id):
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