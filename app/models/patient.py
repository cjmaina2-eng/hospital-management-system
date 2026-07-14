from datetime import datetime
from app import db

class Patient(db.Model):
    __tablename__ = 'patients'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    national_id = db.Column(db.String(20), unique=True, nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(200))
    city = db.Column(db.String(50))
    state = db.Column(db.String(50))
    postal_code = db.Column(db.String(20))
    blood_type = db.Column(db.String(5))
    allergies = db.Column(db.Text)
    emergency_contact_name = db.Column(db.String(100))
    emergency_contact_phone = db.Column(db.String(20))
    emergency_contact_relationship = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_admitted = db.Column(db.Boolean, default=False)
    admission_date = db.Column(db.DateTime, nullable=True)
    discharge_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='Active')  # Active, Admitted, Discharged
    
    user = db.relationship('User', back_populates='patient')
    # Relationships (commented out until those models are defined)
    appointments = db.relationship('Appointment', back_populates='patient', lazy='dynamic')
    medical_records = db.relationship('MedicalRecord', back_populates='patient', lazy='dynamic')
    bills = db.relationship('Bill', back_populates='patient', lazy='dynamic')
    lab_tests = db.relationship('LabTest', back_populates='patient', lazy='dynamic')
    
    # user = db.relationship('User', back_populates='patient')
    
    def __repr__(self):
        return f'<Patient {self.user.first_name} {self.user.last_name}>'