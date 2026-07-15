from app import create_app, db
from app.models import *

# Create the application
application = create_app()

# Create tables and seed on first run (only in production)
with application.app_context():
    try:
        # Check if users table exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if 'users' not in inspector.get_table_names():
            print("Creating database tables...")
            db.create_all()
            print("Tables created successfully!")
            
            # Seed the database
            from seed import seed_database
            print("Seeding database...")
            seed_database()
            print("Seeding complete!")
        else:
            print("Tables already exist, skipping creation.")
    except Exception as e:
        print(f"Database initialization error: {e}")

if __name__ == "__main__":
    application.run()