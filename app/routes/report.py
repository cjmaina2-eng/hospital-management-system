from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app import db
from app.models import Patient, Doctor, Appointment, MedicalRecord, Bill
from datetime import datetime, timedelta
from sqlalchemy import func, extract

bp = Blueprint('report', __name__, url_prefix='/reports')

# Helper: check if user has report access
def has_report_access():
    return current_user.has_role('admin') or current_user.has_role('receptionist') or current_user.has_role('doctor')

@bp.route('/dashboard')
@login_required
def dashboard():
    if not has_report_access():
        return render_template('errors/403.html'), 403
    
    return render_template('report/dashboard.html')

# --- API Endpoints ---

@bp.route('/api/summary')
@login_required
def api_summary():
    if not has_report_access():
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Counts
    total_patients = Patient.query.count()
    total_doctors = Doctor.query.count()
    total_appointments = Appointment.query.count()
    total_bills = Bill.query.count()
    total_revenue = db.session.query(func.sum(Bill.paid_amount)).scalar() or 0.0
    unpaid_bills = Bill.query.filter_by(status='Unpaid').count()
    completed_appointments = Appointment.query.filter_by(status='Completed').count()
    scheduled_appointments = Appointment.query.filter_by(status='Accepted').count()
    
    return jsonify({
        'total_patients': total_patients,
        'total_doctors': total_doctors,
        'total_appointments': total_appointments,
        'total_bills': total_bills,
        'total_revenue': float(total_revenue),
        'unpaid_bills': unpaid_bills,
        'completed_appointments': completed_appointments,
        'scheduled_appointments': scheduled_appointments,
    })

@bp.route('/api/patient_visits')
@login_required
def api_patient_visits():
    if not has_report_access():
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get days parameter (default 30)
    days = request.args.get('days', 30, type=int)
    start_date = datetime.now() - timedelta(days=days)
    
    # Group by day
    results = db.session.query(
        func.date(Appointment.appointment_date).label('date'),
        func.count(Appointment.id).label('count')
    ).filter(Appointment.appointment_date >= start_date).group_by('date').order_by('date').all()
    
    data = {
        'labels': [str(r.date) for r in results],
        'values': [r.count for r in results]
    }
    return jsonify(data)

@bp.route('/api/revenue')
@login_required
def api_revenue():
    if not has_report_access():
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Group by month (or by day if less than 30 days)
    days = request.args.get('days', 30, type=int)
    start_date = datetime.now() - timedelta(days=days)
    
    # We'll group by day for simplicity
    results = db.session.query(
        func.date(Bill.bill_date).label('date'),
        func.sum(Bill.paid_amount).label('revenue')
    ).filter(Bill.bill_date >= start_date).group_by('date').order_by('date').all()
    
    data = {
        'labels': [str(r.date) for r in results],
        'values': [float(r.revenue or 0.0) for r in results]
    }
    return jsonify(data)

@bp.route('/api/appointment_status')
@login_required
def api_appointment_status():
    if not has_report_access():
        return jsonify({'error': 'Unauthorized'}), 403
    
    results = db.session.query(
        Appointment.status,
        func.count(Appointment.id).label('count')
    ).group_by(Appointment.status).all()
    
    data = {
        'labels': [r.status for r in results],
        'values': [r.count for r in results]
    }
    return jsonify(data)

@bp.route('/api/doctor_workload')
@login_required
def api_doctor_workload():
    if not has_report_access():
        return jsonify({'error': 'Unauthorized'}), 403

    results = (
        db.session.query(
            Doctor,
            func.count(Appointment.id).label('appt_count')
        )
        .join(Appointment, Appointment.doctor_id == Doctor.id)
        .group_by(Doctor.id)
        .order_by(func.count(Appointment.id).desc())
        .limit(10)
        .all()
    )

    data = {
        "labels": [],
        "values": []
    }

    for doctor, appt_count in results:
        if doctor.user:
            name = f"Dr. {doctor.user.first_name} {doctor.user.last_name}"
        else:
            name = f"Doctor {doctor.id}"

        data["labels"].append(name)
        data["values"].append(appt_count)

    return jsonify(data)

@bp.route('/api/billing_status')
@login_required
def api_billing_status():
    if not has_report_access():
        return jsonify({'error': 'Unauthorized'}), 403
    
    results = db.session.query(
        Bill.status,
        func.count(Bill.id).label('count'),
        func.sum(Bill.total_amount).label('total_amount')
    ).group_by(Bill.status).all()
    
    data = {
        'labels': [r.status for r in results],
        'counts': [r.count for r in results],
        'amounts': [float(r.total_amount or 0.0) for r in results]
    }
    return jsonify(data)
