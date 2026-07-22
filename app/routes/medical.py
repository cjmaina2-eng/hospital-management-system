from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import MedicalRecord, Patient, Doctor, Appointment
from app.security import can_edit_clinical_details, can_view_clinical_details
from datetime import datetime

bp = Blueprint('medical', __name__, url_prefix='/medical')

def is_medical_staff():
    return current_user.has_role('doctor') or current_user.has_role('nurse')

@bp.route('/patient/<int:patient_id>')
@login_required
def index(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    if not (current_user.has_role('admin') or current_user.has_role('doctor') or current_user.has_role('nurse') or current_user.has_role('receptionist')):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    records = MedicalRecord.query.filter_by(patient_id=patient_id).order_by(MedicalRecord.date.desc()).all()
    return render_template('medical/index.html', patient=patient, records=records, can_view_clinical_details=can_view_clinical_details)

@bp.route('/add/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def add(patient_id):
    if not is_medical_staff():
        flash('Only doctors and nurses can add medical records.', 'danger')
        return redirect(url_for('medical.index', patient_id=patient_id))
    
    patient = Patient.query.get_or_404(patient_id)
    if not can_edit_clinical_details(current_user, patient_id):
        flash('Access denied. You are not authorized to view this patient.', 'danger')
        return redirect(url_for('dashboard.index'))

    doctor = Doctor.query.filter_by(user_id=current_user.id).first() if current_user.has_role('doctor') else None
    
    if request.method == 'POST':
        diagnosis = request.form.get('diagnosis')
        symptoms = request.form.get('symptoms')
        clinical_notes = request.form.get('clinical_notes')
        prescription = request.form.get('prescription')
        lab_requests = request.form.get('lab_requests')
        lab_results = request.form.get('lab_results')
        follow_up_notes = request.form.get('follow_up_notes')
        status = request.form.get('status', 'Active')
        appointment_id = request.form.get('appointment_id')
        
        doctor_id = None
        if current_user.has_role('doctor'):
            if not doctor:
                flash('Doctor profile not found.', 'danger')
                return redirect(url_for('medical.add', patient_id=patient_id))
            doctor_id = doctor.id
        else:
            assigned = Appointment.query.filter_by(patient_id=patient_id).order_by(Appointment.created_at.desc()).first()
            if not assigned:
                flash('A nurse can only add records after a doctor has been assigned through an appointment.', 'danger')
                return redirect(url_for('medical.index', patient_id=patient_id))
            doctor_id = assigned.doctor_id
        
        if appointment_id:
            appt = Appointment.query.get(appointment_id)
            if not appt or appt.patient_id != patient_id:
                flash('Invalid appointment.', 'danger')
                return redirect(url_for('medical.add', patient_id=patient_id))
        
        record = MedicalRecord(
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_id=appointment_id if appointment_id else None,
            diagnosis=diagnosis,
            symptoms=symptoms,
            clinical_notes=clinical_notes,
            prescription=prescription,
            lab_requests=lab_requests,
            lab_results=lab_results,
            follow_up_notes=follow_up_notes,
            status=status
        )
        db.session.add(record)
        if appointment_id:
            appt = Appointment.query.get(appointment_id)
            if appt and appt.status in ['Accepted', 'Scheduled']:
                appt.status = 'Completed'
        db.session.commit()
        flash('Medical record added successfully!', 'success')
        return redirect(url_for('medical.view', record_id=record.id))
    
    # GET: prepare form data
    doctors = None
    appointments = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.status.in_(['Accepted', 'Completed'])
    ).all()
    return render_template('medical/add.html', patient=patient, doctors=doctors, appointments=appointments)

@bp.route('/view/<int:record_id>')
@login_required
def view(record_id):
    record = MedicalRecord.query.get_or_404(record_id)
    patient = record.patient

    if not can_view_clinical_details(current_user, patient.id):
        flash('Access denied. Medical records are confidential.', 'danger')
        return redirect(url_for('dashboard.index'))

    return render_template('medical/view.html', record=record)

@bp.route('/edit/<int:record_id>', methods=['GET', 'POST'])
@login_required
def edit(record_id):
    if not is_medical_staff():
        flash('Only doctors and nurses can edit medical records.', 'danger')
        return redirect(url_for('medical.view', record_id=record_id))
    
    record = MedicalRecord.query.get_or_404(record_id)
    if not can_edit_clinical_details(current_user, record.patient_id):
        flash('Access denied. You are not authorized to edit this record.', 'danger')
        return redirect(url_for('medical.view', record_id=record_id))
    
    if request.method == 'POST':
        record.diagnosis = request.form.get('diagnosis')
        record.symptoms = request.form.get('symptoms')
        record.clinical_notes = request.form.get('clinical_notes')
        record.prescription = request.form.get('prescription')
        record.lab_requests = request.form.get('lab_requests')
        record.lab_results = request.form.get('lab_results')
        record.follow_up_notes = request.form.get('follow_up_notes')
        record.status = request.form.get('status')
        db.session.commit()
        flash('Medical record updated.', 'success')
        return redirect(url_for('medical.view', record_id=record.id))
    
    return render_template('medical/edit.html', record=record)

@bp.route('/delete/<int:record_id>', methods=['POST'])
@login_required
def delete(record_id):
    if not is_medical_staff():
        flash('Permission denied.', 'danger')
        return redirect(url_for('medical.view', record_id=record_id))
    
    record = MedicalRecord.query.get_or_404(record_id)
    if not can_edit_clinical_details(current_user, record.patient_id):
        flash('Access denied. You are not authorized to delete this record.', 'danger')
        return redirect(url_for('medical.view', record_id=record_id))
    
    patient_id = record.patient_id
    db.session.delete(record)
    db.session.commit()
    flash('Record deleted.', 'success')
    return redirect(url_for('medical.index', patient_id=patient_id))
