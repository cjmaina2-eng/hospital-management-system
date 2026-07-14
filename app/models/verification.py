from datetime import datetime, timedelta
from app import db

class VerificationCode(db.Model):
    __tablename__ = 'verification_codes'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<VerificationCode {self.code} for {self.email}>'

    @staticmethod
    def generate_code():
        import random
        return f"{random.randint(100000, 999999)}"

    @staticmethod
    def create_for_email(email):
        # Remove old unused codes for this email
        VerificationCode.query.filter_by(email=email, used=False).delete()
        code = VerificationCode.generate_code()
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        vc = VerificationCode(email=email, code=code, expires_at=expires_at)
        db.session.add(vc)
        db.session.commit()
        return code

    @staticmethod
    def verify(email, code):
        vc = VerificationCode.query.filter_by(email=email, code=code, used=False).first()
        if vc and vc.expires_at > datetime.utcnow():
            vc.used = True
            db.session.commit()
            return True
        return False