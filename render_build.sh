#!/usr/bin/env bash
# exit on error
set -o errexit

# Install required dependencies
pip install -r requirements.txt

# Create tables and seed data
python init_db.py
