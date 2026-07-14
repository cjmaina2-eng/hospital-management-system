from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app import db
from app.models import Patient, Appointment, MedicalRecord, Bill, Doctor
from sqlalchemy import func
from datetime import datetime, timedelta

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@bp.route('/')
@login_required
def index():
    role_names = [role.name for role in current_user.roles]

    # Global stats (visible to all)
    total_patients = Patient.query.count()
    total_appointments = Appointment.query.count()
    total_revenue = db.session.query(func.sum(Bill.paid_amount)).scalar() or 0.0
    unpaid_bills = Bill.query.filter_by(status='Unpaid').count()

    # Recent appointments (last 5 for all)
    recent_appointments = Appointment.query.order_by(Appointment.appointment_date.desc()).limit(5).all()

    # --- Medical Records: restricted access ---
    # Admin and Reception should NOT see medical record content
    if current_user.has_role('patient'):
        # Patient sees only their own records
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        recent_records = MedicalRecord.query.filter_by(patient_id=patient.id)\
            .order_by(MedicalRecord.date.desc()).limit(5).all() if patient else []
    elif current_user.has_role('doctor'):
        # Doctor sees records they created
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
        recent_records = MedicalRecord.query.filter_by(doctor_id=doctor.id)\
            .order_by(MedicalRecord.date.desc()).limit(5).all() if doctor else []
    else:
        # Admin / Reception: NO medical records shown
        recent_records = []

    # Current date for the template
    today = datetime.now()

    # Chart data: Appointment Status
    appointment_statuses = db.session.query(
        Appointment.status,
        func.count(Appointment.id)
    ).group_by(Appointment.status).all()
    
    appointment_status_labels = [status[0] or 'Unknown' for status in appointment_statuses]
    appointment_status_values = [status[1] for status in appointment_statuses]

    # Chart data: Revenue (last 7 days)
    seven_days_ago = today - timedelta(days=7)
    revenue_by_date = db.session.query(
        func.date(Bill.bill_date),
        func.sum(Bill.paid_amount)
    ).filter(Bill.bill_date >= seven_days_ago).group_by(func.date(Bill.bill_date)).all()
    
    revenue_labels = [item[0].strftime('%Y-%m-%d') if item[0] else 'N/A' for item in revenue_by_date]
    revenue_values = [float(item[1]) if item[1] else 0.0 for item in revenue_by_date]

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
        'today': today,
        'appointment_status_labels': appointment_status_labels,
        'appointment_status_values': appointment_status_values,
        'revenue_labels': revenue_labels,
        'revenue_values': revenue_values,
    }
    return render_template('dashboard/index.html', **context)