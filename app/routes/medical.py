from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import MedicalRecord, Patient, Doctor, Appointment
from datetime import datetime

bp = Blueprint('medical', __name__, url_prefix='/medical')

# Helper to check if user is a doctor (or admin) to allow write operations
def is_medical_staff():
    return current_user.has_role('doctor') or current_user.has_role('admin')

@bp.route('/patient/<int:patient_id>')
@login_required
def index(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    # Permissions: patient can view their own; doctor/admin/receptionist can view any
    if current_user.has_role('patient'):
        if patient.user_id != current_user.id:
            flash('You can only view your own medical records.', 'danger')
            return redirect(url_for('dashboard.index'))
    
    records = MedicalRecord.query.filter_by(patient_id=patient_id).order_by(MedicalRecord.date.desc()).all()
    return render_template('medical/index.html', patient=patient, records=records)

@bp.route('/add/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def add(patient_id):
    if not is_medical_staff():
        flash('Only doctors and admins can add medical records.', 'danger')
        return redirect(url_for('medical.index', patient_id=patient_id))
    
    patient = Patient.query.get_or_404(patient_id)
    doctor = Doctor.query.filter_by(user_id=current_user.id).first() if current_user.has_role('doctor') else None
    # Admin can choose doctor or set it to None (we'll handle in form)
    
    if request.method == 'POST':
        # Get form data
        diagnosis = request.form.get('diagnosis')
        symptoms = request.form.get('symptoms')
        clinical_notes = request.form.get('clinical_notes')
        prescription = request.form.get('prescription')
        lab_requests = request.form.get('lab_requests')
        lab_results = request.form.get('lab_results')
        follow_up_notes = request.form.get('follow_up_notes')
        status = request.form.get('status', 'Active')
        appointment_id = request.form.get('appointment_id')
        
        # Determine doctor_id: if admin, use selected doctor or fallback
        doctor_id = None
        if current_user.has_role('admin'):
            doctor_id = request.form.get('doctor_id')
            if doctor_id:
                doctor_id = int(doctor_id)
            else:
                # if none selected, use first doctor? We'll require selection
                flash('Please select a doctor.', 'danger')
                return redirect(url_for('medical.add', patient_id=patient_id))
        else:
            # doctor is logged in
            if not doctor:
                flash('Doctor profile not found.', 'danger')
                return redirect(url_for('medical.add', patient_id=patient_id))
            doctor_id = doctor.id
        
        # Validate appointment_id (optional)
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
        db.session.commit()
        flash('Medical record added successfully!', 'success')
        return redirect(url_for('medical.view', record_id=record.id))
    
    # GET: prepare form data
    doctors = Doctor.query.all() if current_user.has_role('admin') else None
    appointments = Appointment.query.filter_by(patient_id=patient_id, status='Scheduled').all()
    return render_template('medical/add.html', patient=patient, doctors=doctors, appointments=appointments)

@bp.route('/view/<int:record_id>')
@login_required
def view(record_id):
    record = MedicalRecord.query.get_or_404(record_id)
    patient = record.patient

    # Permission checks
    if current_user.has_role('patient'):
        if patient.user_id != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('dashboard.index'))
    elif current_user.has_role('doctor'):
        # Allow if doctor created the record (or optionally if doctor has a relationship)
        if record.doctor.user_id != current_user.id:
            # You might allow any doctor to view, but we restrict to creator only for privacy
            flash('Access denied. You did not create this record.', 'danger')
            return redirect(url_for('dashboard.index'))
    else:
        # Admin or Reception: deny access entirely
        flash('Access denied. Medical records are confidential.', 'danger')
        return redirect(url_for('dashboard.index'))

    return render_template('medical/view.html', record=record)

@bp.route('/edit/<int:record_id>', methods=['GET', 'POST'])
@login_required
def edit(record_id):
    if not is_medical_staff():
        flash('Only doctors and admins can edit medical records.', 'danger')
        return redirect(url_for('medical.view', record_id=record_id))
    
    record = MedicalRecord.query.get_or_404(record_id)
    # Optionally restrict: only the doctor who created it, or admin can edit any
    if current_user.has_role('doctor'):
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
        if not doctor or doctor.id != record.doctor_id:
            flash('You can only edit records you created.', 'danger')
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
    if not current_user.has_role('admin') and not current_user.has_role('doctor'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('medical.view', record_id=record_id))
    
    record = MedicalRecord.query.get_or_404(record_id)
    # Only the creating doctor or admin can delete
    if current_user.has_role('doctor'):
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
        if not doctor or doctor.id != record.doctor_id:
            flash('You can only delete records you created.', 'danger')
            return redirect(url_for('medical.view', record_id=record_id))
    
    patient_id = record.patient_id
    db.session.delete(record)
    db.session.commit()
    flash('Record deleted.', 'success')
    return redirect(url_for('medical.index', patient_id=patient_id))