#!/bin/bash

echo "Starting Secure Biometric System (Django Backend)..."

source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
