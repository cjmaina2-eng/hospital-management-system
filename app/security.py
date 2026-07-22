from app.models import Doctor, Nurse, Patient


CLINICAL_ROLES = ('doctor', 'nurse')


def is_clinical_user(user):
    return any(user.has_role(role) for role in CLINICAL_ROLES)


def is_operational_user(user):
    return user.has_role('admin') or user.has_role('receptionist') or user.has_role('lab_technician')


def is_pharmacy_user(user):
    return user.has_role('pharmacist') or user.has_role('admin')


def is_assigned_doctor_for_patient(user, patient_id):
    if not user.has_role('doctor'):
        return False
    doctor = Doctor.query.filter_by(user_id=user.id).first()
    if not doctor:
        return False
    return doctor.appointments.filter_by(patient_id=patient_id).count() > 0


def is_assigned_nurse():
    return True


def can_view_clinical_details(user, patient_id):
    patient = Patient.query.get(patient_id)
    if not patient:
        return False
    if user.has_role('patient'):
        return patient.user_id == user.id
    if user.has_role('nurse'):
        return True
    if user.has_role('doctor'):
        return is_assigned_doctor_for_patient(user, patient_id)
    return False


def can_view_patient_contact_details(user, patient_id):
    patient = Patient.query.get(patient_id)
    if not patient:
        return False
    if user.has_role('patient'):
        return patient.user_id == user.id
    if user.has_role('nurse'):
        return True
    if user.has_role('doctor'):
        return is_assigned_doctor_for_patient(user, patient_id)
    return False


def can_edit_clinical_details(user, patient_id):
    if user.has_role('nurse'):
        return True
    return is_assigned_doctor_for_patient(user, patient_id)
