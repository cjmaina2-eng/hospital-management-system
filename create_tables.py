"""
create_tables.py
Creates all database tables defined in the models.
Run this after adding new models or if tables are missing.
"""

from app import create_app, db
from app.models import *  # Import all models so they are registered

def create_tables():
    app = create_app()
    with app.app_context():
        db.create_all()
        print("✅ All tables created successfully!")

        # Optional: List existing tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"📋 Existing tables: {', '.join(tables)}")

if __name__ == '__main__':
    create_tables()