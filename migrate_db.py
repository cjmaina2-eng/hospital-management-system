"""
Run this on the server (e.g., via Render shell) to create tables and seed.
"""

from app import create_app, db
from app.models import *

def migrate():
    app = create_app()
    with app.app_context():
        print("Creating tables...")
        db.create_all()
        print("✅ Tables created.")

        # Optionally seed
        from seed import seed_database
        seed_database()
        print("✅ Seeding complete.")

if __name__ == '__main__':
    migrate()