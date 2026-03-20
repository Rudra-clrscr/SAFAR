---
description: Resolution of Supabase connectivity and core configuration issues.
---
# Supabase Troubleshooting Workflow

This workflow is used by Rachit specifically for Supabase-related issues.

1. **Verify `.env` Configuration**
   Check that `DATABASE_URL` is correctly formatted in `.env`. Supabase URLs should typically include `sslmode=require`. Rachit will check if the URL in `.env` matches the expected format.

2. **Check SSL Handshake**
   Supabase requires SSL. Ensure `app.py` has the correct `connect_args` for SQLAlchemy. Rachit will verify `app.py` logic around line 55.

3. **Connectivity Test**
   Execute the diagnostic tool's test:
   ```bash
   python .agent/tools/rachit_db_helper.py --test-connectivity
   ```

4. **Common Fixes**
   - **Protocol mismatch**: If using `postgresql://`, suggest changing to `postgresql+pg8000://` for better SSL support in this project.
   - **Missing Dependencies**: Check if `pg8000` is installed:
     ```bash
     pip show pg8000
     ```

5. **Re-Initialization**
   If the database is connected but empty, consider running:
   ```bash
   python init_db.py
   ```
   *Note:rachit will ask for confirmation before doing this.*
