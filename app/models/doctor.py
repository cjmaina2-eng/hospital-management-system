from datetime import datetime
from app import db

class Doctor(db.Model):
    __tablename__ = 'doctors'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    license_number = db.Column(db.String(50), unique=True, nullable=False)
    years_of_experience = db.Column(db.Integer, default=0)
    department = db.Column(db.String(100))
    status = db.Column(db.String(20), default='free')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', back_populates='doctor')
    appointments = db.relationship('Appointment', back_populates='doctor', lazy='dynamic')
    medical_records = db.relationship('MedicalRecord', back_populates='doctor', lazy='dynamic')
    lab_tests = db.relationship('LabTest', back_populates='doctor', lazy='dynamic')
    
    @property
    def is_available(self):
        return self.status == 'free'
    
    def __repr__(self):
        return f'<Doctor {self.user.first_name} {self.user.last_name} - {self.specialization}>'

class Nurse(db.Model):
    __tablename__ = 'nurses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    license_number = db.Column(db.String(50), unique=True, nullable=False)
    department = db.Column(db.String(100))
    status = db.Column(db.String(20), default='free')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', back_populates='nurse')
    medical_records = db.relationship('MedicalRecord', back_populates='nurse', lazy='dynamic')
    lab_tests = db.relationship('LabTest', back_populates='nurse', lazy='dynamic')
    
    def __repr__(self):
        return f'<Nurse {self.user.first_name} {self.user.last_name}>'