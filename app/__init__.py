from flask import Flask, redirect, render_template, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
from flask_mail import Mail

# Initialize extensions at module level
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Please log in to access this page."

    # Import all models so SQLAlchemy registers them.
    from app.models import (
        Appointment,
        Bill,
        Doctor,
        MedicalRecord,
        Patient,
        Role,
        User,
        VerificationCode,
        LabTest
    )

    # Import and register blueprints.
    from app.routes import appointment, auth, billing, dashboard, doctor, lab, medical, patient, report

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(patient.bp)
    app.register_blueprint(appointment.bp)
    app.register_blueprint(medical.bp)
    app.register_blueprint(billing.bp)
    app.register_blueprint(report.bp)
    app.register_blueprint(doctor.bp)

    app.register_blueprint(lab.bp)


    @app.route('/')
    def index():
        from flask_login import current_user

        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    return app


# User loader (needs to be at module level)
@login_manager.user_loader
def load_user(user_id):
    from app.models import User

    return User.query.get(int(user_id))
