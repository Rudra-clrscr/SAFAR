from app import app, db, seed_safety_zones

def setup_database():
    with app.app_context():
        print("Creating all database tables...")
        db.create_all()
        print("Seeding initial safety zones data...")
        seed_safety_zones()
        print("Database initialized successfully!")

if __name__ == '__main__':
    setup_database()
