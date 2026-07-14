from datetime import datetime
from app import db

class Bill(db.Model):
    __tablename__ = 'bills'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=True)
    bill_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.Date)  # optional
    total_amount = db.Column(db.Numeric(10, 2), default=0.00)
    paid_amount = db.Column(db.Numeric(10, 2), default=0.00)
    status = db.Column(db.String(20), default='Unpaid')  # Paid, Partial, Unpaid, Cancelled
    payment_method = db.Column(db.String(50))  # Cash, Credit Card, Insurance, etc.
    source_type = db.Column(db.String(20), default='Manual')  # Manual, Discharge
    source_id = db.Column(db.Integer, nullable=True)  # For linking to discharge events
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = db.relationship('Patient', back_populates='bills')
    appointment = db.relationship('Appointment')
    items = db.relationship('BillItem', back_populates='bill', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Bill {self.id} - Patient {self.patient_id}>'

class BillItem(db.Model):
    __tablename__ = 'bill_items'

    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)  # quantity * unit_price

    # Optional link to a service or product (we'll keep simple)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bill = db.relationship('Bill', back_populates='items')

    def __repr__(self):
        return f'<BillItem {self.id} - {self.description}>'
