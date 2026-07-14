from app import db
from app.models import Patient, Bill, BillItem, Service, Appointment, LabTest
from decimal import Decimal
from datetime import datetime

class DischargeService:
    @staticmethod
    def generate_bill(patient_id, doctor_id, notes=""):
        """Generate a bill for a discharged patient."""
        patient = Patient.query.get(patient_id)
        if not patient:
            raise ValueError("Patient not found")

        # Check if already discharged
        if patient.status == 'Discharged':
            raise ValueError("Patient already discharged")

        # Calculate total
        total = Decimal('0.00')

        # Create bill
        bill = Bill(
            patient_id=patient_id,
            bill_date=datetime.utcnow(),
            status='Unpaid',
            source_type='Discharge',
            notes=f"Discharge bill - {notes}" if notes else "Discharge bill",
            total_amount=total,
            paid_amount=Decimal('0.00')
        )
        db.session.add(bill)
        db.session.flush()  # Get bill.id

        # --- Add Consultation Fee (if patient had appointments) ---
        appointments = Appointment.query.filter_by(patient_id=patient_id, status='Completed').all()
        if appointments:
            consultation_service = Service.query.filter_by(name='Consultation').first()
            if consultation_service:
                for appt in appointments:
                    item = BillItem(
                        bill_id=bill.id,
                        description=f"Consultation - Dr. {appt.doctor.user.first_name} {appt.doctor.user.last_name}",
                        quantity=1,
                        unit_price=consultation_service.default_price,
                        total=consultation_service.default_price
                    )
                    db.session.add(item)
                    total += consultation_service.default_price

        # --- Add Lab Tests (completed tests) ---
        lab_tests = LabTest.query.filter_by(patient_id=patient_id, status='Completed').all()
        if lab_tests:
            for test in lab_tests:
                # Try to find matching service
                service = Service.query.filter_by(name=f"Lab: {test.test_name}").first()
                price = service.default_price if service else Decimal('50.00')  # Default fallback
                item = BillItem(
                    bill_id=bill.id,
                    description=f"Lab Test: {test.test_name}",
                    quantity=1,
                    unit_price=price,
                    total=price
                )
                db.session.add(item)
                total += price

        # --- Add Procedure / Treatment Fees (from medical records) ---
        # This is simplified – you can add more logic to extract from records
        # Or prompt doctor to add manually

        # Update bill total
        bill.total_amount = total

        # Update patient status
        patient.status = 'Discharged'
        patient.discharge_date = datetime.utcnow()

        db.session.commit()

        # Mark all active appointments as completed
        active_appointments = Appointment.query.filter_by(patient_id=patient_id, status='Scheduled').all()
        for appt in active_appointments:
            appt.status = 'Completed'

        db.session.commit()

        return bill

    @staticmethod
    def notify_reception(bill):
        """Mark bill as ready for reception processing."""
        # This can be used to trigger email or in-app notification
        # For now, we just set a flag – we'll add a 'ready_for_payment' field
        pass