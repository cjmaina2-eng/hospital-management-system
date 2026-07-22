from app import create_app, db
from app.models import *
from sqlalchemy import inspect, text

# Create the application
application = create_app()
app = application


def ensure_compatible_schema():
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    migrations = []

    for table in db.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue

        existing_columns = {column['name'] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.primary_key or column.name in existing_columns:
                continue
            column_type = column.type.compile(dialect=db.engine.dialect)
            migrations.append((table.name, column.name, column_type))

    if migrations:
        with db.engine.begin() as conn:
            for table_name, column_name, column_type in migrations:
                conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}'))
        print(f"Applied {len(migrations)} compatibility schema update(s).")

    inspector = inspect(db.engine)
    if 'appointments' in existing_tables:
        appointment_columns = {column['name'] for column in inspector.get_columns('appointments')}
        if {'appointment_date_requested', 'appointment_date'}.issubset(appointment_columns):
            with db.engine.begin() as conn:
                conn.execute(text("""
                    UPDATE appointments
                    SET appointment_date_requested = DATE(appointment_date)
                    WHERE appointment_date_requested IS NULL
                      AND appointment_date IS NOT NULL
                """))


# Create tables and seed on first run (only in production)
with application.app_context():
    try:
        # Check if users table exists
        inspector = inspect(db.engine)
        first_install = 'users' not in inspector.get_table_names()
        db.create_all()

        if first_install:
            print("Creating database tables...")
            print("Tables created successfully!")
            
            # Seed the database
            from seed import seed_database
            print("Seeding database...")
            seed_database()
            print("Seeding complete!")
        else:
            print("Tables already exist, ensured missing tables are created.")
            ensure_compatible_schema()
    except Exception as e:
        print(f"Database initialization error: {e}")

if __name__ == "__main__":
    application.run()
