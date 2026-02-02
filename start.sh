#!/bin/bash
# Start script for Railway Railpack

# Install Python dependencies
pip install -r requirements.txt

# Start the scheduler
exec python scheduler.py
