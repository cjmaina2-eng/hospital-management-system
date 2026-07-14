from datetime import datetime
from app import db

class LabTest(db.Model):
    __tablename__ = 'lab_tests'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    test_name = db.Column(db.String(200), nullable=False)
    test_description = db.Column(db.Text)
    ordered_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Ordered')  # Ordered, In-Progress, Completed, Cancelled
    result = db.Column(db.Text)  # The lab result text (could be numbers, text, etc.)
    result_date = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text)   # Technician notes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = db.relationship('Patient', back_populates='lab_tests')
    doctor = db.relationship('Doctor', back_populates='lab_tests')

    def __repr__(self):
        return f'<LabTest {self.id} - {self.test_name} for Patient {self.patient_id}>'