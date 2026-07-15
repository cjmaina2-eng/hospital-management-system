from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app import db
from app.models import Patient, Appointment, MedicalRecord, Bill, Doctor
from sqlalchemy import func
from datetime import datetime

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@bp.route('/')
@login_required
def index():
    role_names = [role.name for role in current_user.roles]

    total_patients = Patient.query.count()
    total_appointments = Appointment.query.count()
    total_revenue = db.session.query(func.sum(Bill.paid_amount)).scalar() or 0.0
    unpaid_bills = Bill.query.filter_by(status='Unpaid').count()

    recent_appointments = Appointment.query.order_by(Appointment.appointment_date.desc()).limit(5).all()

    # Medical records – role-restricted
    if current_user.has_role('patient'):
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        recent_records = MedicalRecord.query.filter_by(patient_id=patient.id)\
            .order_by(MedicalRecord.date.desc()).limit(5).all() if patient else []
    elif current_user.has_role('doctor'):
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
        recent_records = MedicalRecord.query.filter_by(doctor_id=doctor.id)\
            .order_by(MedicalRecord.date.desc()).limit(5).all() if doctor else []
    else:
        recent_records = []

    # --- Doctor-specific: pending appointments ---
    pending_appointments = []
    upcoming_appointments = []
    if current_user.has_role('doctor'):
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
        if doctor:
            pending_appointments = Appointment.query.filter_by(
                doctor_id=doctor.id,
                status='Pending'
            ).order_by(Appointment.appointment_date.asc()).all()
            
            upcoming_appointments = Appointment.query.filter(
                Appointment.doctor_id == doctor.id,
                Appointment.status.in_(['Accepted', 'Scheduled']),
                Appointment.appointment_date >= datetime.now()
            ).order_by(Appointment.appointment_date.asc()).all()

    today = datetime.now()

    context = {
        'user': current_user,
        'roles': role_names,
        'is_admin': 'admin' in role_names,
        'is_doctor': 'doctor' in role_names,
        'is_nurse': 'nurse' in role_names,
        'is_receptionist': 'receptionist' in role_names,
        'total_patients': total_patients,
        'total_appointments': total_appointments,
        'total_revenue': total_revenue,
        'unpaid_bills': unpaid_bills,
        'recent_appointments': recent_appointments,
        'recent_records': recent_records,
        'pending_appointments': pending_appointments,
        'upcoming_appointments': upcoming_appointments,
        'today': today,
    }
    return render_template('dashboard/index.html', **context)