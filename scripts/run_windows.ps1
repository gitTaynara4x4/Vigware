Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force

if (!(Test-Path ".venv")) {
  py -m venv .venv
}

& ".\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip setuptools wheel
python -m pip install --no-cache-dir -r requirements.txt

$env:DATABASE_URL = (Get-Content .env | Where-Object { $_ -match '^DATABASE_URL=' }) -replace '^DATABASE_URL=', ''
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8002
