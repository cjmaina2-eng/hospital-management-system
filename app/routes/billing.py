from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Bill, BillItem, Patient, Appointment
from app.services.mpesa_service import MpesaService
from decimal import Decimal
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('billing', __name__, url_prefix='/billing')

def is_billing_staff():
    """Only receptionist and admin can perform billing operations"""
    return current_user.has_role('admin') or current_user.has_role('receptionist')

@bp.route('/')
@login_required
def index():
    # Admin/receptionist see all; doctor sees all (read-only); patient sees own
    if current_user.has_role('patient'):
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        if not patient:
            flash('Patient profile not found.', 'danger')
            return redirect(url_for('dashboard.index'))
        bills = Bill.query.filter_by(patient_id=patient.id).order_by(Bill.bill_date.desc()).all()
    else:
        # All bills for staff
        bills = Bill.query.order_by(Bill.bill_date.desc()).all()
    return render_template('billing/index.html', bills=bills)

@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if not is_billing_staff():
        flash('Only admin and receptionist can create bills.', 'danger')
        return redirect(url_for('billing.index'))
    
    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        appointment_id = request.form.get('appointment_id')
        due_date = request.form.get('due_date')
        notes = request.form.get('notes')
        payment_method = request.form.get('payment_method')
        
        # Validate patient
        patient = Patient.query.get(patient_id)
        if not patient:
            flash('Patient not found.', 'danger')
            return redirect(url_for('billing.new'))
        
        # Create bill
        bill = Bill(
            patient_id=patient_id,
            appointment_id=appointment_id if appointment_id else None,
            due_date=datetime.strptime(due_date, '%Y-%m-%d').date() if due_date else None,
            notes=notes,
            payment_method=payment_method,
            status='Unpaid',
            total_amount=0.00,
            paid_amount=0.00
        )
        db.session.add(bill)
        db.session.flush()  # get bill.id for line items
        
        # Process line items from dynamic fields
        descriptions = request.form.getlist('description[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        
        total = Decimal('0.00')
        for desc, qty, price in zip(descriptions, quantities, unit_prices):
            if desc.strip() and qty and price:
                qty = int(qty)
                price = Decimal(price)
                item_total = qty * price
                item = BillItem(
                    bill_id=bill.id,
                    description=desc,
                    quantity=qty,
                    unit_price=price,
                    total=item_total
                )
                db.session.add(item)
                total += item_total
        
        # Update bill total
        bill.total_amount = total
        db.session.commit()
        flash('Bill created successfully!', 'success')
        return redirect(url_for('billing.view', bill_id=bill.id))
    
    # GET: prepare form data
    patients = Patient.query.all()
    appointments = Appointment.query.filter_by(status='Scheduled').all()
    return render_template('billing/new.html', patients=patients, appointments=appointments)

@bp.route('/view/<int:bill_id>')
@login_required
def view(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    # Permission: patient can only see own; staff can see all
    if current_user.has_role('patient'):
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        if not patient or patient.id != bill.patient_id:
            flash('Access denied.', 'danger')
            return redirect(url_for('billing.index'))
    return render_template('billing/view.html', bill=bill)

@bp.route('/edit/<int:bill_id>', methods=['GET', 'POST'])
@login_required
def edit(bill_id):
    if not is_billing_staff():
        flash('Permission denied.', 'danger')
        return redirect(url_for('billing.index'))
    
    bill = Bill.query.get_or_404(bill_id)
    if bill.status == 'Paid':
        flash('Paid bills cannot be edited.', 'warning')
        return redirect(url_for('billing.view', bill_id=bill.id))
    
    if request.method == 'POST':
        # Update header
        bill.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date() if request.form.get('due_date') else None
        bill.notes = request.form.get('notes')
        bill.payment_method = request.form.get('payment_method')
        # Update status? Usually status is updated via payment recording.
        # We can update total if we allow item editing (we'll keep it simple: items are managed separately)
        db.session.commit()
        flash('Bill updated.', 'success')
        return redirect(url_for('billing.view', bill_id=bill.id))
    
    return render_template('billing/edit.html', bill=bill)

@bp.route('/add_item/<int:bill_id>', methods=['POST'])
@login_required
def add_item(bill_id):
    if not is_billing_staff():
        flash('Permission denied.', 'danger')
        return redirect(url_for('billing.view', bill_id=bill_id))
    
    bill = Bill.query.get_or_404(bill_id)
    if bill.status == 'Paid':
        flash('Cannot add items to a paid bill.', 'warning')
        return redirect(url_for('billing.view', bill_id=bill_id))
    
    description = request.form.get('description')
    quantity = int(request.form.get('quantity', 1))
    unit_price = Decimal(request.form.get('unit_price', '0.00'))
    
    if description and unit_price > 0:
        item_total = quantity * unit_price
        item = BillItem(
            bill_id=bill.id,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            total=item_total
        )
        db.session.add(item)
        # Update bill total
        bill.total_amount += item_total
        db.session.commit()
        flash('Item added.', 'success')
    else:
        flash('Invalid item.', 'danger')
    return redirect(url_for('billing.view', bill_id=bill_id))

@bp.route('/remove_item/<int:item_id>', methods=['POST'])
@login_required
def remove_item(item_id):
    if not is_billing_staff():
        flash('Permission denied.', 'danger')
        return redirect(url_for('billing.index'))
    
    item = BillItem.query.get_or_404(item_id)
    bill = item.bill
    if bill.status == 'Paid':
        flash('Cannot remove from a paid bill.', 'warning')
        return redirect(url_for('billing.view', bill_id=bill.id))
    
    # Update bill total
    bill.total_amount -= item.total
    db.session.delete(item)
    db.session.commit()
    flash('Item removed.', 'success')
    return redirect(url_for('billing.view', bill_id=bill.id))

@bp.route('/record_payment/<int:bill_id>', methods=['POST'])
@login_required
def record_payment(bill_id):
    if not is_billing_staff():
        flash('Permission denied.', 'danger')
        return redirect(url_for('billing.index'))
    
    bill = Bill.query.get_or_404(bill_id)
    if bill.status == 'Paid':
        flash('Bill already paid.', 'warning')
        return redirect(url_for('billing.view', bill_id=bill_id))
    
    amount = Decimal(request.form.get('amount', '0.00'))
    if amount <= 0:
        flash('Invalid amount.', 'danger')
        return redirect(url_for('billing.view', bill_id=bill_id))
    
    # Update paid amount
    new_paid = bill.paid_amount + amount
    if new_paid >= bill.total_amount:
        bill.paid_amount = bill.total_amount
        bill.status = 'Paid'
    else:
        bill.paid_amount = new_paid
        bill.status = 'Partial' if new_paid > 0 else 'Unpaid'
    db.session.commit()
    flash('Payment recorded.', 'success')
    return redirect(url_for('billing.view', bill_id=bill_id))

@bp.route('/<int:bill_id>/pay', methods=['GET'])
@login_required
def pay(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    # Permission: patient can pay their own bills; admin/reception can pay any
    if current_user.has_role('patient'):
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        if not patient or patient.id != bill.patient_id:
            flash('You can only pay your own bills.', 'danger')
            return redirect(url_for('billing.index'))
    elif not (current_user.has_role('admin') or current_user.has_role('receptionist')):
        flash('Permission denied.', 'danger')
        return redirect(url_for('billing.index'))

    if bill.status == 'Paid':
        flash('This bill is already fully paid.', 'warning')
        return redirect(url_for('billing.view', bill_id=bill.id))

    return render_template('billing/pay.html', bill=bill)

@bp.route('/delete/<int:bill_id>', methods=['POST'])
@login_required
def delete(bill_id):
    if not current_user.has_role('admin'):
        flash('Only admin can delete bills.', 'danger')
        return redirect(url_for('billing.index'))
    
    bill = Bill.query.get_or_404(bill_id)
    if bill.status == 'Paid':
        flash('Cannot delete a paid bill.', 'warning')
        return redirect(url_for('billing.view', bill_id=bill_id))
    db.session.delete(bill)
    db.session.commit()
    flash('Bill deleted.', 'success')
    return redirect(url_for('billing.index'))

@bp.route('/pending')
@login_required
def pending():
    if not (current_user.has_role('admin') or current_user.has_role('receptionist')):
        flash('Access denied.', 'danger')
        return redirect(url_for('billing.index'))

    bills = Bill.query.filter_by(status='Unpaid').order_by(Bill.bill_date.desc()).all()
    return render_template('billing/pending.html', bills=bills)


@bp.route('/mpesa/initiate/<int:bill_id>', methods=['POST'])
@login_required
def mpesa_initiate(bill_id):
    """Initiate M-Pesa STK push payment"""
    bill = Bill.query.get_or_404(bill_id)
    
    # Permission: patient can pay own bills, reception/admin can process any
    if current_user.has_role('patient'):
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        if not patient or patient.id != bill.patient_id:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    elif not (current_user.has_role('admin') or current_user.has_role('receptionist')):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    if bill.status == 'Paid':
        return jsonify({'status': 'error', 'message': 'Bill already paid'}), 400
    
    try:
        phone_number = request.form.get('phone_number', '')
        if not phone_number:
            return jsonify({'status': 'error', 'message': 'Phone number required'}), 400
        
        # Initialize M-Pesa service
        mpesa_service = MpesaService()
        
        # Initiate STK push
        response = mpesa_service.initiate_stk_push(
            phone_number=phone_number,
            amount=float(bill.total_amount),
            bill_id=bill.id,
            party_name=f"Hospital Bill #{bill.id}"
        )
        
        # Check if request was successful
        if response.get('ResponseCode') == '0':
            # Store checkout request ID
            bill.mpesa_checkout_request_id = response.get('CheckoutRequestID')
            bill.mpesa_phone_number = phone_number
            bill.payment_method = 'M-Pesa'
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'STK push sent successfully',
                'checkout_request_id': response.get('CheckoutRequestID')
            })
        else:
            return jsonify({
                'status': 'error',
                'message': response.get('ResponseDescription', 'STK push failed')
            }), 400
            
    except Exception as e:
        logger.error(f"M-Pesa initiation error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/mpesa/callback', methods=['POST'])
def mpesa_callback():
    """Handle M-Pesa callback from Daraja"""
    try:
        callback_data = request.get_json()
        
        # Process callback
        transaction_data = MpesaService.process_callback(callback_data)
        
        if transaction_data['status'] == 'success':
            # Find bill by checkout request ID
            checkout_id = transaction_data.get('checkout_request_id')
            bill = Bill.query.filter_by(mpesa_checkout_request_id=checkout_id).first()
            
            if bill:
                # Update bill with transaction details
                bill.mpesa_receipt_number = transaction_data.get('mpesa_receipt_number')
                bill.mpesa_transaction_date = datetime.utcnow()
                
                # Update payment status
                amount_paid = transaction_data.get('transaction_amount', Decimal('0.00'))
                bill.paid_amount = amount_paid
                bill.payment_method = 'M-Pesa'
                
                if amount_paid >= bill.total_amount:
                    bill.status = 'Paid'
                else:
                    bill.status = 'Partial'
                
                db.session.commit()
                logger.info(f"Bill {bill.id} payment received via M-Pesa: {amount_paid}")
        
        # Always return 200 to acknowledge receipt
        return jsonify({'ResultCode': '0', 'ResultDesc': 'Callback received'}), 200
        
    except Exception as e:
        logger.error(f"M-Pesa callback error: {str(e)}")
        return jsonify({'ResultCode': '1', 'ResultDesc': 'Error'}), 500


@bp.route('/mpesa/check_status/<int:bill_id>', methods=['GET'])
@login_required
def mpesa_check_status(bill_id):
    """Check status of M-Pesa payment"""
    bill = Bill.query.get_or_404(bill_id)
    
    # Permission check
    if current_user.has_role('patient'):
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        if not patient or patient.id != bill.patient_id:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    elif not (current_user.has_role('admin') or current_user.has_role('receptionist')):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    try:
        if not bill.mpesa_checkout_request_id:
            return jsonify({
                'status': 'error',
                'message': 'No M-Pesa transaction in progress'
            }), 400
        
        mpesa_service = MpesaService()
        status_response = mpesa_service.query_transaction_status(bill.mpesa_checkout_request_id)
        
        return jsonify({
            'status': 'success',
            'bill_status': bill.status,
            'amount_paid': float(bill.paid_amount),
            'total_amount': float(bill.total_amount),
            'mpesa_status': status_response
        })
        
    except Exception as e:
        logger.error(f"Error checking M-Pesa status: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
