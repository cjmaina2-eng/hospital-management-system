from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db, mail
from app.models import LabTest, Patient, Doctor, User
from datetime import datetime
from flask_mail import Message
from flask import current_app

bp = Blueprint('lab', __name__, url_prefix='/lab')

def is_lab_staff():
    return current_user.has_role('admin') or current_user.has_role('doctor') or current_user.has_role('lab_technician')

@bp.route('/')
@login_required
def index():
    # Redirect based on role
    if current_user.has_role('doctor'):
        # Show tests ordered by this doctor
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
        if not doctor:
            flash('Doctor profile not found.', 'danger')
            return redirect(url_for('dashboard.index'))
        tests = LabTest.query.filter_by(doctor_id=doctor.id).order_by(LabTest.ordered_date.desc()).all()
        return render_template('lab/index.html', tests=tests, role='doctor')

    elif current_user.has_role('lab_technician') or current_user.has_role('admin'):
        # Show all pending / in-progress tests
        tests = LabTest.query.filter(LabTest.status.in_(['Ordered', 'In-Progress'])).order_by(LabTest.ordered_date.asc()).all()
        return render_template('lab/index.html', tests=tests, role='technician')

    else:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.index'))

@bp.route('/order/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def order(patient_id):
    if not current_user.has_role('doctor') and not current_user.has_role('admin'):
        flash('Only doctors can order lab tests.', 'danger')
        return redirect(url_for('dashboard.index'))

    patient = Patient.query.get_or_404(patient_id)
    doctor = Doctor.query.filter_by(user_id=current_user.id).first() if current_user.has_role('doctor') else None

    if request.method == 'POST':
        test_name = request.form.get('test_name')
        description = request.form.get('description')

        if not test_name:
            flash('Test name is required.', 'danger')
            return redirect(url_for('lab.order', patient_id=patient_id))

        # Determine doctor_id
        doctor_id = None
        if current_user.has_role('admin'):
            doctor_id = request.form.get('doctor_id')
            if not doctor_id:
                flash('Please select a doctor.', 'danger')
                return redirect(url_for('lab.order', patient_id=patient_id))
        else:
            if not doctor:
                flash('Doctor profile not found.', 'danger')
                return redirect(url_for('dashboard.index'))
            doctor_id = doctor.id

        lab_test = LabTest(
            patient_id=patient_id,
            doctor_id=doctor_id,
            test_name=test_name,
            test_description=description,
            status='Ordered'
        )
        db.session.add(lab_test)
        db.session.commit()

        flash('Lab test ordered successfully.', 'success')
        return redirect(url_for('lab.index'))

    # GET: prepare form
    doctors = Doctor.query.all() if current_user.has_role('admin') else None
    return render_template('lab/order.html', patient=patient, doctors=doctors)

@bp.route('/view/<int:test_id>')
@login_required
def view(test_id):
    test = LabTest.query.get_or_404(test_id)
    # Permissions: doctor who ordered, patient (own), admin, lab_technician
    if current_user.has_role('patient'):
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        if not patient or patient.id != test.patient_id:
            flash('Access denied.', 'danger')
            return redirect(url_for('dashboard.index'))
    elif current_user.has_role('doctor'):
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
        if doctor and doctor.id != test.doctor_id:
            # Allow any doctor? For simplicity, allow all doctors to view any test? We'll restrict.
            # Actually, doctors might need to see results from other doctors; we can allow all doctors to view.
            # We'll allow all doctors for now.
            pass
    elif current_user.has_role('lab_technician') or current_user.has_role('admin'):
        pass
    else:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.index'))

    return render_template('lab/view.html', test=test)

@bp.route('/enter_result/<int:test_id>', methods=['GET', 'POST'])
@login_required
def enter_result(test_id):
    if not current_user.has_role('lab_technician') and not current_user.has_role('admin'):
        flash('Only lab technicians can enter results.', 'danger')
        return redirect(url_for('lab.index'))

    test = LabTest.query.get_or_404(test_id)
    if test.status in ['Completed', 'Cancelled']:
        flash('This test is already completed or cancelled.', 'warning')
        return redirect(url_for('lab.view', test_id=test_id))

    if request.method == 'POST':
        result = request.form.get('result')
        notes = request.form.get('notes')
        status = request.form.get('status')

        if not result:
            flash('Result is required.', 'danger')
            return redirect(url_for('lab.enter_result', test_id=test_id))

        test.result = result
        test.notes = notes
        test.status = status or 'Completed'
        test.result_date = datetime.utcnow()

        db.session.commit()

        # --- Send email notification to the ordering doctor ---
        try:
            doctor_user = test.doctor.user
            patient = test.patient
            subject = f"Lab Result Ready: {test.test_name} for {patient.user.first_name} {patient.user.last_name}"
            html_body = f"""
<p>Dear Dr. {doctor_user.first_name},</p>
<p>The lab results for <strong>{patient.user.first_name} {patient.user.last_name}</strong> are ready.</p>
<p><strong>Test:</strong> {test.test_name}</p>
<p><strong>Result:</strong> {result}</p>
<p>You can view the full details <a href="{url_for('lab.view', test_id=test.id, _external=True)}">here</a>.</p>
<p>Thank you,<br>Lab Department</p>
            """
            msg = Message(
                subject=subject,
                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=[doctor_user.email],
                html=html_body
            )
            mail.send(msg)
            flash('Result saved and doctor notified via email.', 'success')
        except Exception as e:
            # Log error but don't fail the request
            current_app.logger.error(f"Failed to send email: {e}")
            flash('Result saved but email notification failed.', 'warning')

        return redirect(url_for('lab.view', test_id=test_id))

    return render_template('lab/enter_result.html', test=test)

@bp.route('/update_status/<int:test_id>', methods=['POST'])
@login_required
def update_status(test_id):
    if not current_user.has_role('lab_technician') and not current_user.has_role('admin'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('lab.index'))

    test = LabTest.query.get_or_404(test_id)
    status = request.form.get('status')
    if status in ['Ordered', 'In-Progress', 'Completed', 'Cancelled']:
        test.status = status
        db.session.commit()
        flash('Status updated.', 'success')
    else:
        flash('Invalid status.', 'danger')
    return redirect(url_for('lab.view', test_id=test_id))

@bp.route('/delete/<int:test_id>', methods=['POST'])
@login_required
def delete(test_id):
    if not current_user.has_role('admin'):
        flash('Only admins can delete tests.', 'danger')
        return redirect(url_for('lab.index'))

    test = LabTest.query.get_or_404(test_id)
    db.session.delete(test)
    db.session.commit()
    flash('Test deleted.', 'success')
    return redirect(url_for('lab.index'))