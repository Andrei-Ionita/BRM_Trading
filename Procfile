# Railway Procfile - Define services to run
# See: https://docs.railway.app/deploy/procfile

# Dashboard web service (main)
web: gunicorn --chdir dashboard app:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120

# Trading scheduler - handles both DA (at 12:00) and IDM (every 15 min)
scheduler: python scheduler.py

# Alternative: Run DA and IDM as separate services
# da: python day_ahead_automation.py
# idm: python intraday_automation.py --interval-minutes 15
