import os
import ssl

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

load_dotenv()

database_url = (os.environ.get("DATABASE_URL") or "").strip()
if not database_url:
    raise SystemExit("Missing DATABASE_URL in .env.")

engine_url = make_url(database_url)
print(
    f"[Supabase Test] Host={engine_url.host} Port={engine_url.port} Database={engine_url.database}"
)

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

connect_args = {"timeout": float(os.environ.get("DB_CONNECT_TIMEOUT", "20"))}
if "pg8000" in database_url:
    connect_args["ssl_context"] = ssl_context

try:
    engine = create_engine(database_url, connect_args=connect_args)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("SUCCESS: Supabase connection is working.")
except Exception as exc:
    print(f"FAILED: {exc}")
    print("Tip: verify the password, pooler host, and network access.")
