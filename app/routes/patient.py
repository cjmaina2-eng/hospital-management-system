from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Role, Patient
from datetime import datetime
from app.services.discharge_service import DischargeService

bp = Blueprint('patient', __name__, url_prefix='/patients')

def admin_or_receptionist_required():
    """Helper to check if user is admin or receptionist"""
    return current_user.has_role('admin') or current_user.has_role('receptionist')

@bp.route('/')
@login_required
def index():
    # Allow admin, doctor, receptionist to view patient list
    if not (current_user.has_role('admin') or current_user.has_role('doctor') or current_user.has_role('receptionist')):
        flash('You do not have permission to view patients.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    patients = Patient.query.all()
    return render_template('patient/index.html', patients=patients)

@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    # Only admin and receptionist can create patients
    if not admin_or_receptionist_required():
        flash('You do not have permission to register patients.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        # Get user data
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        
        # Get patient data
        national_id = request.form.get('national_id')
        date_of_birth = request.form.get('date_of_birth')
        gender = request.form.get('gender')
        phone = request.form.get('phone')
        address = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        postal_code = request.form.get('postal_code')
        blood_type = request.form.get('blood_type')
        allergies = request.form.get('allergies')
        emergency_contact_name = request.form.get('emergency_contact_name')
        emergency_contact_phone = request.form.get('emergency_contact_phone')
        emergency_contact_relationship = request.form.get('emergency_contact_relationship')
        
        # Validate email uniqueness
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('patient.new'))
        
        # Create user with role 'patient'
        patient_role = Role.query.filter_by(name='patient').first()
        if not patient_role:
            flash('Patient role not found. Please run seed.', 'danger')
            return redirect(url_for('patient.new'))
        
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=True
        )
        user.set_password(password)
        user.roles.append(patient_role)
        db.session.add(user)
        db.session.flush()  # to get user.id
        
        # Create patient record
        patient = Patient(
            user_id=user.id,
            national_id=national_id,
            date_of_birth=datetime.strptime(date_of_birth, '%Y-%m-%d').date(),
            gender=gender,
            phone=phone,
            address=address,
            city=city,
            state=state,
            postal_code=postal_code,
            blood_type=blood_type,
            allergies=allergies,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
            emergency_contact_relationship=emergency_contact_relationship
        )
        db.session.add(patient)
        db.session.commit()
        
        flash('Patient registered successfully!', 'success')
        return redirect(url_for('patient.index'))
    
    return render_template('patient/new.html')

@bp.route('/<int:id>')
@login_required
def view(id):
    if not (current_user.has_role('admin') or current_user.has_role('doctor') or current_user.has_role('receptionist')):
        flash('Permission denied.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    patient = Patient.query.get_or_404(id)
    return render_template('patient/view.html', patient=patient)

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not admin_or_receptionist_required():
        flash('Permission denied.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    patient = Patient.query.get_or_404(id)
    user = patient.user
    
    if request.method == 'POST':
        # Update user fields
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        # Optionally update email? Might be better to prevent email change for simplicity.
        # Update patient fields
        patient.national_id = request.form.get('national_id')
        patient.date_of_birth = datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d').date()
        patient.gender = request.form.get('gender')
        patient.phone = request.form.get('phone')
        patient.address = request.form.get('address')
        patient.city = request.form.get('city')
        patient.state = request.form.get('state')
        patient.postal_code = request.form.get('postal_code')
        patient.blood_type = request.form.get('blood_type')
        patient.allergies = request.form.get('allergies')
        patient.emergency_contact_name = request.form.get('emergency_contact_name')
        patient.emergency_contact_phone = request.form.get('emergency_contact_phone')
        patient.emergency_contact_relationship = request.form.get('emergency_contact_relationship')
        
        db.session.commit()
        flash('Patient updated successfully!', 'success')
        return redirect(url_for('patient.view', id=patient.id))
    
    return render_template('patient/edit.html', patient=patient, user=user)

@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not current_user.has_role('admin'):
        flash('Only admins can delete patients.', 'danger')
        return redirect(url_for('patient.index'))
    
    patient = Patient.query.get_or_404(id)
    user = patient.user
    db.session.delete(patient)
    db.session.delete(user)  # Also delete the user account
    db.session.commit()
    flash('Patient deleted successfully.', 'success')
    return redirect(url_for('patient.index'))

@bp.route('/<int:id>/discharge', methods=['GET', 'POST'])
@login_required
def discharge(id):
    # Only doctors and admins can discharge
    if not (current_user.has_role('doctor') or current_user.has_role('admin')):
        flash('Only doctors and admins can discharge patients.', 'danger')
        return redirect(url_for('patient.view', id=id))

    patient = Patient.query.get_or_404(id)

    if patient.status == 'Discharged':
        flash('Patient already discharged.', 'warning')
        return redirect(url_for('patient.view', id=id))

    if request.method == 'POST':
        notes = request.form.get('notes', '')

        try:
            bill = DischargeService.generate_bill(patient.id, current_user.id, notes)
            flash(f'Patient discharged successfully. Bill #{bill.id} created.', 'success')
            return redirect(url_for('billing.view', bill_id=bill.id))
        except Exception as e:
            flash(f'Error discharging patient: {str(e)}', 'danger')
            return redirect(url_for('patient.view', id=id))

    return render_template('patient/discharge.html', patient=patient)
