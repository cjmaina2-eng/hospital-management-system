from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app import db
from app.models import Patient, Appointment, MedicalRecord, Bill, Doctor, LabTest, Nurse
from sqlalchemy import func
from datetime import datetime, date

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@bp.route('/')
@login_required
def index():
    role_names = [role.name for role in current_user.roles]

    today = datetime.now()
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today.replace(hour=23, minute=59, second=59, microsecond=999999)
    today_date = date.today()

    total_patients = Patient.query.count()
    total_appointments = Appointment.query.count()
    total_revenue = db.session.query(func.sum(Bill.paid_amount)).scalar() or 0.0
    outstanding_balance = db.session.query(func.sum(Bill.total_amount - Bill.paid_amount)).filter(
        Bill.status.in_(['Unpaid', 'Partial'])
    ).scalar() or 0.0
    unpaid_bills = Bill.query.filter_by(status='Unpaid').count()
    pharmacy_pickups = len([bill for bill in Bill.query.filter_by(status='Paid').all() if bill.medication_items and bill.pharmacy_status != 'Dispensed'])
    admitted_patients = Patient.query.filter_by(is_admitted=True).count()
    pending_lab_tests = LabTest.query.filter(LabTest.status.in_(['Ordered', 'In-Progress'])).count()
    pending_appointment_count = Appointment.query.filter_by(status='Pending').count()
    accepted_appointment_count = Appointment.query.filter_by(status='Accepted').count()
    completed_appointment_count = Appointment.query.filter_by(status='Completed').count()

    bookings_today = Appointment.query.filter(
        Appointment.appointment_date_requested >= today_start.date(),
        Appointment.appointment_date_requested <= today_end.date()
    ).count()

    pending_payments_blocking = len([bill for bill in Bill.query.filter(Bill.status.in_(['Unpaid', 'Partial'])).all() if bill.medication_items])

    appointments_today = Appointment.query.filter(
        Appointment.appointment_date_requested == today.date()
    ).count()

    recent_appointments = Appointment.query.order_by(
        Appointment.appointment_date_requested.desc(),
        Appointment.appointment_date.desc()
    ).limit(5).all()

    if current_user.has_role('patient'):
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        recent_records = MedicalRecord.query.filter_by(patient_id=patient.id)\
            .order_by(MedicalRecord.date.desc()).limit(5).all() if patient else []
        patient_bills = Bill.query.filter_by(patient_id=patient.id).order_by(Bill.bill_date.desc()).limit(5).all() if patient else []
        upcoming_patient_appointments = Appointment.query.filter(
            Appointment.patient_id == patient.id,
            Appointment.status.in_(['Pending', 'Accepted', 'Scheduled']),
            Appointment.appointment_date >= today
        ).order_by(Appointment.appointment_date.asc()).all() if patient else []
        medical_record_count = MedicalRecord.query.filter_by(patient_id=patient.id).count() if patient else 0
    else:
        recent_records = []
        patient_bills = []
        upcoming_patient_appointments = []
        medical_record_count = 0

    pending_appointments = []
    upcoming_appointments = []
    my_patients_count = 0
    my_completed_today = 0
    if current_user.has_role('doctor'):
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
        if doctor:
            pending_appointments = Appointment.query.filter_by(
                doctor_id=doctor.id,
                status='Pending'
            ).order_by(Appointment.appointment_date_requested.asc()).all()

            upcoming_appointments = Appointment.query.filter(
                Appointment.doctor_id == doctor.id,
                Appointment.status.in_(['Accepted', 'Scheduled']),
                Appointment.appointment_date >= datetime.now()
            ).order_by(Appointment.appointment_date.asc()).all()

            my_patients_count = db.session.query(func.count(func.distinct(Appointment.patient_id))).filter(
                Appointment.doctor_id == doctor.id
            ).scalar() or 0

            my_completed_today = Appointment.query.filter(
                Appointment.doctor_id == doctor.id,
                Appointment.status == 'Completed',
                Appointment.appointment_date >= today_start,
                Appointment.appointment_date <= today_end
            ).count()

    revenue_today = db.session.query(func.sum(Bill.paid_amount)).filter(
        Bill.updated_at >= today_start,
        Bill.updated_at <= today_end,
        Bill.status == 'Paid'
    ).scalar() or 0.0

    pending_bills = Bill.query.filter_by(status='Unpaid').limit(5).all()
    paid_bills_pharmacy = Bill.query.filter(
        Bill.status == 'Paid',
        Bill.pharmacy_status == 'Ready'
    ).limit(5).all()

    dispensed_today = len([bill for bill in Bill.query.filter(
        Bill.updated_at >= today_start,
        Bill.updated_at <= today_end
    ).all() if bill.medication_items and bill.pharmacy_status == 'Dispensed'])

    pending_discharges = Patient.query.filter_by(is_admitted=True).limit(5).all()
    lab_tests_today = LabTest.query.filter(
        LabTest.ordered_date >= today_start,
        LabTest.ordered_date <= today_end
    ).count()

    pending_tests = LabTest.query.filter(LabTest.status.in_(['Ordered', 'In-Progress'])).limit(5).all()
    completed_tests_today = LabTest.query.filter(
        LabTest.status == 'Completed',
        LabTest.result_date >= today_start,
        LabTest.result_date <= today_end
    ).count()

    nurse_patients = []
    nurse_lab_tests_pending = []
    nurse_appointments_today = []
    if current_user.has_role('nurse'):
        nurse = Nurse.query.filter_by(user_id=current_user.id).first()
        if nurse:
            nurse_patients = Patient.query.filter_by(is_admitted=True).all()
            nurse_lab_tests_pending = LabTest.query.filter(LabTest.status.in_(['Ordered', 'In-Progress'])).all()
            nurse_appointments_today = Appointment.query.filter(
                Appointment.appointment_date_requested == today_date
            ).all()

    my_pending_appointments = pending_appointments
    my_upcoming_appointments = upcoming_appointments
    my_completed_appointments_today = []
    my_lab_tests_count = 0
    if current_user.has_role('doctor'):
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
        if doctor:
            my_completed_appointments_today = Appointment.query.filter(
                Appointment.doctor_id == doctor.id,
                Appointment.status == 'Completed',
                Appointment.appointment_date >= today_start,
                Appointment.appointment_date <= today_end
            ).all()
            my_lab_tests_count = LabTest.query.filter_by(doctor_id=doctor.id).filter(
                LabTest.status.in_(['Ordered', 'In-Progress'])
            ).count()

    pharmacy_ready = 0
    pharmacy_dispensed = 0
    pharmacy_blocked_by_payment = 0
    if current_user.has_role('pharmacist'):
        pharmacy_ready = len([b for b in Bill.query.filter_by(status='Paid').all() if b.medication_items and b.pharmacy_status != 'Dispensed'])
        pharmacy_dispensed = len([b for b in Bill.query.filter_by(status='Paid').all() if b.medication_items and b.pharmacy_status == 'Dispensed'])
        pharmacy_blocked_by_payment = len([b for b in Bill.query.filter(Bill.status.in_(['Unpaid','Partial'])).all() if b.medication_items])

    my_unpaid_bills = []
    my_recent_records = []
    my_upcoming_patient_appointments = []
    if current_user.has_role('patient'):
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        if patient:
            my_unpaid_bills = Bill.query.filter_by(patient_id=patient.id).filter(Bill.status.in_(['Unpaid', 'Partial'])).all()
            my_recent_records = MedicalRecord.query.filter_by(patient_id=patient.id).order_by(MedicalRecord.date.desc()).limit(5).all()
            my_upcoming_patient_appointments = Appointment.query.filter(
                Appointment.patient_id == patient.id,
                Appointment.status.in_(['Accepted', 'Scheduled']),
                Appointment.appointment_date >= datetime.now()
            ).order_by(Appointment.appointment_date.asc()).all()

    pending_lab_tests_list = []
    completed_tests_today_list = []
    orders_received = []
    if current_user.has_role('lab_technician'):
        pending_lab_tests_list = LabTest.query.filter(LabTest.status.in_(['Ordered', 'In-Progress'])).limit(5).all()
        completed_tests_today_list = LabTest.query.filter(
            LabTest.status == 'Completed',
            LabTest.result_date >= today_start,
            LabTest.result_date <= today_end
        ).limit(5).all()
        orders_received = LabTest.query.filter(LabTest.status == 'Ordered').limit(5).all()

    context = {
        'user': current_user,
        'roles': role_names,
        'is_admin': 'admin' in role_names,
        'is_doctor': 'doctor' in role_names,
        'is_nurse': 'nurse' in role_names,
        'is_receptionist': 'receptionist' in role_names,
        'is_pharmacist': 'pharmacist' in role_names,
        'is_patient': 'patient' in role_names,
        'is_lab_technician': 'lab_technician' in role_names,
        'total_patients': total_patients,
        'total_appointments': total_appointments,
        'total_revenue': total_revenue,
        'outstanding_balance': outstanding_balance,
        'unpaid_bills': unpaid_bills,
        'pharmacy_pickups': pharmacy_pickups,
        'admitted_patients': admitted_patients,
        'pending_lab_tests': pending_lab_tests,
        'pending_appointment_count': pending_appointment_count,
        'accepted_appointment_count': accepted_appointment_count,
        'completed_appointment_count': completed_appointment_count,
        'recent_appointments': recent_appointments,
        'recent_records': recent_records,
        'pending_appointments': pending_appointments,
        'upcoming_appointments': upcoming_appointments,
        'today': today,
        'bookings_today': bookings_today,
        'revenue_today': revenue_today,
        'pending_bills': pending_bills,
        'paid_bills_pharmacy': paid_bills_pharmacy,
        'patient_bills': patient_bills,
        'upcoming_patient_appointments': upcoming_patient_appointments,
        'medical_record_count': medical_record_count,
        'my_patients_count': my_patients_count,
        'my_completed_today': my_completed_today,
        'pending_discharges': pending_discharges,
        'lab_tests_today': lab_tests_today,
        'pending_payments_blocking': pending_payments_blocking,
        'dispensed_today': dispensed_today,
        'pending_tests': pending_tests,
        'completed_tests_today': completed_tests_today,
        'appointments_today': appointments_today,
        'my_pending_appointments': my_pending_appointments,
        'my_upcoming_appointments': my_upcoming_appointments,
        'my_completed_appointments_today': my_completed_appointments_today,
        'my_lab_tests_count': my_lab_tests_count,
        'nurse_patients': nurse_patients,
        'nurse_lab_tests_pending': nurse_lab_tests_pending,
        'nurse_appointments_today': nurse_appointments_today,
        'pharmacy_ready': pharmacy_ready,
        'pharmacy_dispensed': pharmacy_dispensed,
        'pharmacy_blocked_by_payment': pharmacy_blocked_by_payment,
        'my_upcoming_patient_appointments': my_upcoming_patient_appointments,
        'my_unpaid_bills': my_unpaid_bills,
        'my_recent_records': my_recent_records,
        'pending_lab_tests_list': pending_lab_tests_list,
        'completed_tests_today_list': completed_tests_today_list,
        'orders_received': orders_received,
    }
    return render_template('dashboard/index.html', **context)
