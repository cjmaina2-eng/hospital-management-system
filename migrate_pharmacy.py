"""
Adds pharmacy pickup tracking columns to existing databases.

Run:
    python migrate_pharmacy.py
"""

from sqlalchemy import inspect, text

from app import create_app, db


def migrate_pharmacy():
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        columns = [column['name'] for column in inspector.get_columns('bills')]
        timestamp_type = 'TIMESTAMP' if db.engine.dialect.name == 'postgresql' else 'DATETIME'

        with db.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO roles (name, description)
                SELECT 'pharmacist', 'Pharmacist'
                WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = 'pharmacist')
            """))

            if 'pharmacy_status' not in columns:
                conn.execute(text("ALTER TABLE bills ADD COLUMN pharmacy_status VARCHAR(20) DEFAULT 'Not Required'"))
                print("Added bills.pharmacy_status")

            if 'medication_released_at' not in columns:
                conn.execute(text(f"ALTER TABLE bills ADD COLUMN medication_released_at {timestamp_type}"))
                print("Added bills.medication_released_at")

            if 'medication_released_by' not in columns:
                conn.execute(text("ALTER TABLE bills ADD COLUMN medication_released_by INTEGER"))
                print("Added bills.medication_released_by")

            conn.execute(text("""
                UPDATE bills
                SET pharmacy_status = 'Ready'
                WHERE status = 'Paid'
                  AND id IN (
                    SELECT bill_id FROM bill_items
                    WHERE lower(description) LIKE '%mg%'
                       OR lower(description) LIKE '%tablet%'
                       OR lower(description) LIKE '%capsule%'
                       OR lower(description) LIKE '%syrup%'
                       OR lower(description) LIKE '%inhaler%'
                       OR lower(description) LIKE '%injection%'
                       OR lower(description) LIKE '%dose%'
                  )
                  AND (pharmacy_status IS NULL OR pharmacy_status = 'Not Required')
            """))

        print("Pharmacy migration complete.")


if __name__ == '__main__':
    migrate_pharmacy()
