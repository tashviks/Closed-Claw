@echo off
echo Setting up ClosedClaw backend...

python -m venv venv
call venv\Scripts\activate.bat

pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Backend setup complete!
echo Run: venv\Scripts\activate.bat ^&^& uvicorn main:app --host 127.0.0.1 --port 8765
