"""
Discharge Service – generates bills for patients being discharged.
Automatically adds:
- Consultation Fee (1,000 KES)
- Completed Lab Tests
- Medications (selected by the doctor)
"""

from datetime import datetime
from decimal import Decimal

from app import db
from app.models import Patient, Bill, BillItem, Service, LabTest, Appointment


class DischargeService:
    @staticmethod
    def generate_bill(patient_id, doctor_id, medication_items=None, notes=""):
        """
        Generate a bill for a discharged patient.

        Args:
            patient_id (int): ID of the patient being discharged.
            doctor_id (int): ID of the discharging doctor (unused, but kept for future).
            medication_items (list): List of dicts, each with:
                - 'service_id': int (ID of the medication Service)
                - 'quantity': int (number of units)
            notes (str): Optional notes to add to the bill.

        Returns:
            Bill: The created Bill object.
        """
        # --- Fetch patient ---
        patient = Patient.query.get(patient_id)
        if not patient:
            raise ValueError("Patient not found")

        if patient.status == 'Discharged':
            raise ValueError("Patient already discharged")

        # --- Create the bill ---
        total = Decimal('0.00')
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
        db.session.flush()  # ensures bill.id is available for line items

        # --- 1) Consultation Fee (always 1,000 KES) ---
        consultation_service = Service.query.filter_by(name='Consultation Fee').first()
        if consultation_service:
            item = BillItem(
                bill_id=bill.id,
                description="Consultation Fee (Standard)",
                quantity=1,
                unit_price=consultation_service.default_price,
                total=consultation_service.default_price
            )
            db.session.add(item)
            total += consultation_service.default_price
        else:
            # Fallback if service is missing (shouldn't happen after seeding)
            item = BillItem(
                bill_id=bill.id,
                description="Consultation Fee",
                quantity=1,
                unit_price=Decimal('1000.00'),
                total=Decimal('1000.00')
            )
            db.session.add(item)
            total += Decimal('1000.00')

        # --- 2) Completed Lab Tests ---
        lab_tests = LabTest.query.filter_by(patient_id=patient_id, status='Completed').all()
        for test in lab_tests:
            # Try to find a matching Service entry (named "Lab: <test_name>")
            service = Service.query.filter_by(name=f"Lab: {test.test_name}").first()
            price = service.default_price if service else Decimal('50.00')  # fallback price
            item = BillItem(
                bill_id=bill.id,
                description=f"Lab Test: {test.test_name}",
                quantity=1,
                unit_price=price,
                total=price
            )
            db.session.add(item)
            total += price

        # --- 3) Medications (selected by doctor) ---
        if medication_items:
            for med in medication_items:
                service = Service.query.get(med['service_id'])
                if service and service.category == 'Medication':
                    qty = med['quantity']
                    item_total = service.default_price * qty
                    item = BillItem(
                        bill_id=bill.id,
                        description=f"{service.name} (x{qty})",
                        quantity=qty,
                        unit_price=service.default_price,
                        total=item_total
                    )
                    db.session.add(item)
                    total += item_total

        # --- Update bill total ---
        bill.total_amount = total

        # --- Update patient status ---
        patient.status = 'Discharged'
        patient.discharge_date = datetime.utcnow()

        # --- (Optional) Mark any scheduled appointments as completed ---
        active_appointments = Appointment.query.filter_by(
            patient_id=patient_id,
            status='Scheduled'
        ).all()
        for appt in active_appointments:
            appt.status = 'Completed'

        # --- Commit everything ---
        db.session.commit()

        return bill