"""
BRM Trading Bot - Main Entry Point for Railway
"""
import os
import sys

# Determine which service to run based on environment variable
service = os.environ.get("RAILWAY_SERVICE_NAME", "scheduler")

if service == "web" or os.environ.get("PORT"):
    # Run web dashboard
    from dashboard.app import app
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
else:
    # Run scheduler (default)
    from scheduler import main
    main()
