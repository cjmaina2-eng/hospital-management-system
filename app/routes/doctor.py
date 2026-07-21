from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Appointment, Doctor

bp = Blueprint('doctor', __name__, url_prefix='/doctor')

@bp.route('/status', methods=['GET', 'POST'])
@login_required
def status():
    # Only doctors and admins can update status
    if not (current_user.has_role('doctor') or current_user.has_role('admin')):
        flash('Permission denied.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    # Get the doctor record
    if current_user.has_role('doctor'):
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    else:  # admin can select which doctor
        doctor_id = request.args.get('doctor_id') or request.form.get('doctor_id')
        if doctor_id:
            doctor = Doctor.query.get(doctor_id)
        else:
            flash('Please select a doctor.', 'warning')
            return redirect(url_for('admin.doctors'))  # Need an admin doctor list
    
    if not doctor:
        flash('Doctor profile not found.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        new_status = request.form.get('status')
        if new_status in ['free', 'in_session', 'on_leave', 'lunch_break', 'in_surgery']:
            doctor.status = new_status
            db.session.commit()
            flash(f'Status updated to {new_status.replace("_", " ").title()}.', 'success')
        else:
            flash('Invalid status.', 'danger')
        return redirect(url_for('doctor.status'))
    
    pending_appointments = (
        Appointment.query
        .filter_by(doctor_id=doctor.id, status='Pending')
        .order_by(Appointment.appointment_date.asc())
        .all()
    )

    # GET: show form
    return render_template('doctor/status.html', doctor=doctor, pending_appointments=pending_appointments)

# Also add a route for admin to list doctors (optional)
