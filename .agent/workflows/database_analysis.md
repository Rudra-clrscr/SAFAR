---
description: Deep-dive analysis of the SAFAR project database.
---
# Database Analysis Workflow

This workflow is used by Rachit to perform a comprehensive health check of the SAFAR database.

1. **Test Connectivity**
   Run the following command to ensure the database is reachable:
   ```bash
   python .agent/tools/rachit_db_helper.py --test-connectivity
   ```

2. **Analyze Schema and Row Counts**
   Run this command to inspect the current state of tables:
   ```bash
   python .agent/tools/rachit_db_helper.py --analyze-schema
   ```

3. **Check for "Core" Data Problems**
   Run this command to check for missing tables or empty critical datasets:
   ```bash
   python .agent/tools/rachit_db_helper.py --check-problems
   ```

4. **Examine Anomalies**
   If connectivity is OK but the app is failing, check the `anomalies` table for recent logs:
   ```bash
   # Rachit will run a custom query if needed to see recent anomalies
   ```

5. **Report Generation**
   Rachit will summarize the findings and propose fixes for any discrepancies.
