import sys
from app import create_app, db
from app.models import *
from seed import seed_database

def reset_db(seed=False, force=False):
    """
    Drop all tables and recreate them.
    If seed=True, also run the seed script to populate with sample data.
    If force=True, skip the confirmation prompt.
    """
    app = create_app()
    with app.app_context():
        if not force:
            confirm = input("⚠️  This will DELETE ALL DATA in the database. Continue? (y/n): ")
            if confirm.lower() != 'y':
                print("Operation cancelled.")
                return

        print("🔄 Dropping all tables...")
        db.drop_all()
        print("✅ All tables dropped.")

        print("🔨 Creating all tables...")
        db.create_all()
        print("✅ Tables created.")

        if seed:
            print("🌱 Seeding database...")
            seed_database()
            print("✅ Seed completed.")

        print("🎉 Database reset successful!")

if __name__ == "__main__":
    # Parse command-line arguments
    seed = "--seed" in sys.argv
    force = "--force" in sys.argv
    reset_db(seed=seed, force=force)