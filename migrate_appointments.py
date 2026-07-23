"""
Migration script to update appointment table structure.
Converts appointment booking from time-selection at booking to date-selection with time assigned by doctor.

Run this script to update the database schema:
    python migrate_appointments.py
"""

from app import create_app, db
from sqlalchemy import inspect, text

def migrate_appointments():
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('appointments')]
        
        print("Current appointments table columns:", columns)
        
        # Check if we need to add new columns
        if 'appointment_date_requested' not in columns:
            print("\n✓ Adding appointment_date_requested column...")
            with db.engine.begin() as conn:
                # Add new columns
                if 'appointment_date_requested' not in columns:
                    conn.execute(text('ALTER TABLE appointments ADD COLUMN appointment_date_requested DATE'))
                    print("  appointment_date_requested added")
                
                if 'appointment_time' not in columns:
                    conn.execute(text('ALTER TABLE appointments ADD COLUMN appointment_time VARCHAR(5)'))
                    print("  appointment_time added")
                
                # Migrate existing data: set appointment_date_requested to date part of appointment_date
                print("\nMigrating existing appointment data...")
                conn.execute(text('''
                    UPDATE appointments 
                    SET appointment_date_requested = CAST(appointment_date AS DATE)
                    WHERE appointment_date_requested IS NULL
                '''))
                print("  appointment_date_requested populated from appointment_date")
                
                # Extract time and store it
                conn.execute(text('''
                    UPDATE appointments 
                    SET appointment_time = CAST(appointment_date AS TIME(0)) 
                    WHERE appointment_time IS NULL AND appointment_date IS NOT NULL
                '''))
                print("  appointment_time extracted from appointment_date")
        
        print("\n✅ Migration complete!")
        print("Note: appointment_date will now be NULL for pending appointments")
        print("      and will be set when the doctor accepts and assigns a time.")

if __name__ == '__main__':
    migrate_appointments()
