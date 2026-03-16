from app import app, db, seed_safety_zones

def reset_database():
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        print("Creating all database tables...")
        db.create_all()
        print("Seeding initial safety zones data...")
        seed_safety_zones()
        print("Database reset successfully! All old data has been deleted and the database is ready for new values.")

if __name__ == '__main__':
    reset_database()
