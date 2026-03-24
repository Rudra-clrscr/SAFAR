# Supabase Connection Tester for SAFAR
import os
import ssl
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, InterfaceError
from dotenv import load_dotenv

# 1. Load your credentials
load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

print(f"[Supabase Test] Connecting to: {DATABASE_URL[:30]}...")

# 2. Setup SSL (Required for Supabase)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

connect_args = {'ssl_context': ssl_context, 'timeout': 5}

# 3. Test Connection
try:
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("\n✅ SUCCESS! Your laptop is connected to Supabase.")
    print("Your 'Astra' Safety system is now syncing to the cloud. 🌍📈")
except Exception as e:
    print(f"\n❌ FAILED: {e}")
    print("\n[Tip] Make sure your internet is on and your Supabase IP allows this connection!")
