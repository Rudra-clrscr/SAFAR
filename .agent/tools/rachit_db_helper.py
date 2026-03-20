import os
import sys
import argparse
from sqlalchemy import text
from dotenv import load_dotenv

# Add the parent directory to sys.path so we can import app and database
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from app import app, db
    from database import User, Tourist, Group, Destination
    APP_IMPORT_SUCCESS = True
except ImportError as e:
    print(f"Warning: Could not import app or database. {e}")
    APP_IMPORT_SUCCESS = False

def test_connectivity():
    print("--- Connectivity Test ---")
    load_dotenv()
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Error: DATABASE_URL not found in environment.")
        return False
    
    print(f"Attempting to connect to: {db_url.split('@')[-1]}") # Log host only for safety
    
    try:
        if APP_IMPORT_SUCCESS:
            with app.app_context():
                result = db.session.execute(text("SELECT 1")).fetchone()
                if result and result[0] == 1:
                    print("Success: SQLAlchemy connection verified.")
                    return True
        else:
            # Fallback to direct SQLAlchemy engine if app import failed
            from sqlalchemy import create_engine
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connect_args = {}
            if "pg8000" in db_url:
                connect_args['ssl_context'] = ssl_context
                
            engine = create_engine(db_url, connect_args=connect_args)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).fetchone()
                if result and result[0] == 1:
                    print("Success: Raw SQLAlchemy connection verified.")
                    return True
    except Exception as e:
        print(f"Failure: Connection error: {e}")
        return False

def analyze_schema():
    print("\n--- Schema Analysis ---")
    if not APP_IMPORT_SUCCESS:
        print("Error: App import failed, cannot analyze schema via models.")
        return

    with app.app_context():
        try:
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"Found {len(tables)} tables: {', '.join(tables)}")
            
            for table in tables:
                row_count = db.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                print(f" - Table '{table}': {row_count} rows")
        except Exception as e:
            print(f"Error during schema analysis: {e}")

def check_core_problems():
    print("\n--- Core Problem Check ---")
    if not APP_IMPORT_SUCCESS:
        print("Error: App import failed, cannot check core problems.")
        return

    with app.app_context():
        # 1. Check if tables exist
        try:
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            required_tables = ['users', 'tourists', 'groups', 'destinations', 'alerts', 'anomalies']
            missing = [t for t in required_tables if t not in existing_tables]
            if missing:
                print(f"CRITICAL: Missing tables: {', '.join(missing)}")
            else:
                print("Pass: All required tables exist.")
        except Exception as e:
            print(f"Error checking tables: {e}")

        # 2. Check for empty critical tables
        try:
            user_count = db.session.query(User).count()
            if user_count == 0:
                print("Warning: No users found in database.")
            else:
                print(f"Pass: {user_count} users found.")
        except Exception as e:
            print(f"Error checking users: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Rachit Database Helper")
    parser.add_argument('--test-connectivity', action='store_true', help="Test connection to Supabase")
    parser.add_argument('--analyze-schema', action='store_true', help="Analyze database schema and row counts")
    parser.add_argument('--check-problems', action='store_true', help="Check for core database problems")
    parser.add_argument('--all', action='store_true', help="Run all diagnostics")

    args = parser.parse_args()

    if args.all or args.test_connectivity:
        test_connectivity()
    if args.all or args.analyze_schema:
        analyze_schema()
    if args.all or args.check_problems:
        check_core_problems()
    
    if not any(vars(args).values()):
        parser.print_help()
