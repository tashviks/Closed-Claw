@echo off
echo ClosedClaw Setup
echo ==============

where node >nul 2>&1 || (echo Node.js not found. Install from https://nodejs.org && exit /b 1)
where python >nul 2>&1 || (echo Python not found. Install from https://python.org && exit /b 1)

echo Installing frontend dependencies...
npm install

echo Setting up Python backend...
cd backend
call setup.bat
cd ..

echo.
echo Setup complete!
echo.
echo To run: npm run dev
