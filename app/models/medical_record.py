from datetime import datetime
from app import db

class MedicalRecord(db.Model):
    __tablename__ = 'medical_records'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    nurse_id = db.Column(db.Integer, db.ForeignKey('nurses.id'), nullable=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=True)

    date = db.Column(db.DateTime, default=datetime.utcnow)
    diagnosis = db.Column(db.Text)
    symptoms = db.Column(db.Text)
    clinical_notes = db.Column(db.Text)
    prescription = db.Column(db.Text)          # e.g., "Amoxicillin 500mg, 3x daily, 7 days"
    lab_requests = db.Column(db.Text)          # e.g., "CBC, Chest X-Ray"
    lab_results = db.Column(db.Text)           # e.g., "WBC normal, X-Ray clear"
    follow_up_notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='Active')  # Active, Resolved, etc.

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = db.relationship('Patient', back_populates='medical_records')
    doctor = db.relationship('Doctor', back_populates='medical_records')
    nurse = db.relationship('Nurse', back_populates='medical_records')
    appointment = db.relationship('Appointment', back_populates='medical_record')

    def __repr__(self):
        return f'<MedicalRecord {self.id} for Patient {self.patient_id}>'