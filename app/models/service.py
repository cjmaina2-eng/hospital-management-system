from app import db

class Service(db.Model):
    __tablename__ = 'services'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    default_price = db.Column(db.Numeric(10, 2), nullable=False)
    category = db.Column(db.String(50))  # Consultation, Lab, Procedure, Room, etc.
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Service {self.name} - ${self.default_price}>'