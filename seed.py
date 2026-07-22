from app import create_app, db
from app.models import User, Role, Patient, Doctor, Appointment, Service, LabTest, MedicalRecord, Bill, BillItem
from datetime import datetime, timedelta

def seed_database():
    app = create_app()
    with app.app_context():
        # 1. Create roles
        roles = [
            Role(name='admin', description='System Administrator'),
            Role(name='doctor', description='Medical Doctor'),
            Role(name='nurse', description='Nurse'),
            Role(name='receptionist', description='Receptionist'),
            Role(name='patient', description='Patient'),
            Role(name='lab_technician', description='Lab Technician'),
            Role(name='pharmacist', description='Pharmacist')
        ]
        for role in roles:
            if not Role.query.filter_by(name=role.name).first():
                db.session.add(role)
        db.session.commit()

        # Create admin
        admin_email = 'kirwarahospital373@gmail.com'
        legacy_admin_emails = ['admin@kirwarahospital.com', 'admin@hospital.com']
        existing_admin = User.query.filter_by(email=admin_email).first()
        admin = next(
            (User.query.filter_by(email=email).first() for email in legacy_admin_emails),
            None
        )
        if admin and not existing_admin:
            admin.email = admin_email
        elif not existing_admin:
            admin = User(
                email=admin_email,
                first_name='Kirwara',
                last_name='Admin',
                is_active=True
            )
            admin.set_password('admin123')
            admin.roles.append(Role.query.filter_by(name='admin').first())
            db.session.add(admin)

        # 3. Create doctor
        if not User.query.filter_by(email='doctor@hospital.com').first():
            doctor_user = User(
                email='doctor@hospital.com',
                first_name='Sarah',
                last_name='Johnson',
                is_active=True
            )
            doctor_user.set_password('doctor123')
            doctor_user.roles.append(Role.query.filter_by(name='doctor').first())
            db.session.add(doctor_user)
            db.session.flush()  # to get user.id

            doctor = Doctor(
                user_id=doctor_user.id,
                specialization='Cardiology',
                license_number='DOC123456',
                years_of_experience=10,
                department='Cardiology',
                status='free'  # free, in_session, on_leave, lunch_break, in_surgery
            )
            db.session.add(doctor)
        db.session.commit()

        # 4. Create patient
        if not User.query.filter_by(email='patient@example.com').first():
            patient_user = User(
                email='patient@example.com',
                first_name='John',
                last_name='Doe',
                is_active=True
            )
            patient_user.set_password('patient123')
            patient_user.roles.append(Role.query.filter_by(name='patient').first())
            db.session.add(patient_user)
            db.session.flush()

            patient = Patient(
                user_id=patient_user.id,
                national_id='12345678',
                date_of_birth=datetime(1990, 1, 1).date(),
                gender='Male',
                phone='+1234567890',
                address='123 Main St',
                city='Metropolis',
                state='NY',
                postal_code='10001',
                blood_type='A+',
                allergies='None',
                status='Active'
            )
            db.session.add(patient)
        db.session.commit()

        # 5. Create lab technician
        if not User.query.filter_by(email='lab@hospital.com').first():
            lab_user = User(
                email='lab@hospital.com',
                first_name='Lab',
                last_name='Tech',
                is_active=True
            )
            lab_user.set_password('lab123')
            lab_user.roles.append(Role.query.filter_by(name='lab_technician').first())
            db.session.add(lab_user)
        db.session.commit()

        if not User.query.filter_by(email='pharmacy@hospital.com').first():
            pharmacy_user = User(
                email='pharmacy@hospital.com',
                first_name='Pharmacy',
                last_name='Desk',
                is_active=True
            )
            pharmacy_user.set_password('pharmacy123')
            pharmacy_user.roles.append(Role.query.filter_by(name='pharmacist').first())
            db.session.add(pharmacy_user)
        db.session.commit()

        # 6. Create services
        services = [
            Service(name='Consultation', description='Standard consultation fee', default_price=150.00, category='Consultation'),
            Service(name='Lab: CBC', description='Complete Blood Count', default_price=85.00, category='Lab'),
            Service(name='Lab: X-Ray', description='X-Ray imaging', default_price=120.00, category='Lab'),
            Service(name='Lab: COVID-19 Test', description='COVID-19 PCR Test', default_price=95.00, category='Lab'),
            Service(name='Lab: Urinalysis', description='Urine analysis', default_price=50.00, category='Lab'),
            Service(name='Lab: Blood Sugar', description='Blood glucose test', default_price=40.00, category='Lab'),
            Service(name='Procedure: Minor Surgery', description='Minor surgical procedure', default_price=450.00, category='Procedure'),
            Service(name='Room: Standard', description='Standard ward room per day', default_price=200.00, category='Room'),
            Service(name='Room: Private', description='Private room per day', default_price=350.00, category='Room'),
            Service(name='Room: ICU', description='ICU room per day', default_price=800.00, category='Room'),
        ]
        for service in services:
            if not Service.query.filter_by(name=service.name).first():
                db.session.add(service)
        db.session.commit()

        # 7. Create sample appointment (if patient and doctor exist)
        patient = Patient.query.first()
        doctor = Doctor.query.first()
        if patient and doctor:
            if not Appointment.query.filter_by(patient_id=patient.id, doctor_id=doctor.id).first():
                appointment_datetime = datetime.now() + timedelta(days=2, hours=10)
                appt = Appointment(
                    patient_id=patient.id,
                    doctor_id=doctor.id,
                    appointment_date=appointment_datetime,
                    appointment_date_requested=appointment_datetime.date(),
                    appointment_time=appointment_datetime.strftime('%H:%M'),
                    reason='Routine checkup',
                    status='Accepted'
                )
                db.session.add(appt)
                db.session.commit()

        # 8. Create sample medical record
        if patient and doctor:
            if not MedicalRecord.query.filter_by(patient_id=patient.id).first():
                record = MedicalRecord(
                    patient_id=patient.id,
                    doctor_id=doctor.id,
                    diagnosis='Hypertension',
                    symptoms='Headache, dizziness',
                    prescription='Lisinopril 10mg daily',
                    status='Active'
                )
                db.session.add(record)
                db.session.commit()

        # Consultation fee (standard for every discharge)
        if not Service.query.filter_by(name='Consultation Fee').first():
            consultation = Service(
                name='Consultation Fee',
                description='Standard consultation and check-up fee',
                default_price=1000.00,
                category='Consultation'
            )
            db.session.add(consultation)

        # Medications
        medications = [
            Service(name='Paracetamol 500mg', description='Pain reliever and fever reducer', default_price=50.00, category='Medication'),
            Service(name='Amoxicillin 500mg', description='Antibiotic', default_price=120.00, category='Medication'),
            Service(name='Ibuprofen 400mg', description='Anti-inflammatory', default_price=80.00, category='Medication'),
            Service(name='Omeprazole 20mg', description='Acid reducer', default_price=100.00, category='Medication'),
            Service(name='Cetirizine 10mg', description='Antihistamine', default_price=60.00, category='Medication'),
            Service(name='Metformin 500mg', description='Diabetes medication', default_price=90.00, category='Medication'),
            Service(name='Lisinopril 10mg', description='Blood pressure medication', default_price=110.00, category='Medication'),
            Service(name='Atorvastatin 20mg', description='Cholesterol reducer', default_price=130.00, category='Medication'),
            Service(name='Salbutamol Inhaler', description='Asthma relief', default_price=250.00, category='Medication'),
            Service(name='Diclofenac 50mg', description='Pain reliever', default_price=70.00, category='Medication'),
        ]
        for med in medications:
            if not Service.query.filter_by(name=med.name).first():
                db.session.add(med)

        print("✅ Database seeded successfully!")
        print(f"Admin: {admin_email} / admin123")
        print("Doctor: doctor@hospital.com / doctor123")
        print("Patient: patient@example.com / patient123")
        print("Lab Technician: lab@hospital.com / lab123")
        print("Pharmacist: pharmacy@hospital.com / pharmacy123")
        print("Services added: Consultation, Lab tests, etc.")

if __name__ == '__main__':
    seed_database()
