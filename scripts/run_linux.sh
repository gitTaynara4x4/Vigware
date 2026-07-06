#!/usr/bin/env bash
set -e
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install --no-cache-dir -r requirements.txt
export DATABASE_URL=$(grep '^DATABASE_URL=' .env | sed 's/^DATABASE_URL=//')
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8002
