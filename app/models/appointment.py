from datetime import datetime
from app import db

class Appointment(db.Model):
    __tablename__ = 'appointments'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=True)  # Set only after doctor accepts and assigns time
    appointment_date_requested = db.Column(db.Date, nullable=False)  # Date requested by patient (without time)
    appointment_time = db.Column(db.String(5), nullable=True)  # Time assigned by doctor (HH:MM format)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Pending')  # Pending, Accepted, Rejected, Completed, Cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('Patient', back_populates='appointments')
    doctor = db.relationship('Doctor', back_populates='appointments')
    medical_record = db.relationship('MedicalRecord', back_populates='appointment', uselist=False)
    
    def __repr__(self):
        return f'<Appointment {self.id}: {self.patient.user.first_name} with Dr. {self.doctor.user.last_name} - {self.status}>'