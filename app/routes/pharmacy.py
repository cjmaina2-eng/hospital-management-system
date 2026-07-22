from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Bill, Service


bp = Blueprint('pharmacy', __name__, url_prefix='/pharmacy')


def is_pharmacy_staff():
    return current_user.has_role('pharmacist') or current_user.has_role('admin')


@bp.route('/')
@login_required
def index():
    if not is_pharmacy_staff():
        flash('Access denied. Pharmacy pickup is for pharmacy staff only.', 'danger')
        return redirect(url_for('dashboard.index'))

    paid_bills = Bill.query.filter_by(status='Paid').order_by(Bill.bill_date.desc()).all()
    pickup_bills = [bill for bill in paid_bills if bill.medication_items]
    ready_bills = [bill for bill in pickup_bills if bill.pharmacy_status != 'Dispensed']
    dispensed_bills = [bill for bill in pickup_bills if bill.pharmacy_status == 'Dispensed']

    return render_template(
        'pharmacy/index.html',
        bills=pickup_bills,
        ready_bills=ready_bills,
        dispensed_bills=dispensed_bills
    )


@bp.route('/<int:bill_id>')
@login_required
def view(bill_id):
    if not is_pharmacy_staff():
        flash('Access denied. Pharmacy pickup is for pharmacy staff only.', 'danger')
        return redirect(url_for('dashboard.index'))

    bill = Bill.query.get_or_404(bill_id)
    if bill.status != 'Paid' or not bill.medication_items:
        flash('Medication pickup is available only after payment is complete.', 'warning')
        return redirect(url_for('pharmacy.index'))

    medications = Service.query.filter_by(category='Medication').all()
    services = {m.name: m for m in medications}

    return render_template('pharmacy/view.html', bill=bill, services=services)


@bp.route('/<int:bill_id>/dispense', methods=['POST'])
@login_required
def dispense(bill_id):
    if not is_pharmacy_staff():
        flash('Access denied. Pharmacy pickup is for pharmacy staff only.', 'danger')
        return redirect(url_for('dashboard.index'))

    bill = Bill.query.get_or_404(bill_id)
    if bill.status != 'Paid':
        flash('Medication cannot be released until payment is complete.', 'danger')
        return redirect(url_for('pharmacy.view', bill_id=bill.id))

    if not bill.medication_items:
        flash('This bill has no medication items for pickup.', 'warning')
        return redirect(url_for('pharmacy.index'))

    bill.pharmacy_status = 'Dispensed'
    bill.medication_released_at = datetime.utcnow()
    bill.medication_released_by = current_user.id
    db.session.commit()

    flash('Medication pickup marked as dispensed.', 'success')
    return redirect(url_for('pharmacy.view', bill_id=bill.id))
