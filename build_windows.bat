@echo off
echo NCP Storage Manager - Windows Build Script
echo ==========================================

REM 가상환경 활성화 (선택사항)
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM 의존성 설치
echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

REM 빌드 실행
echo Building for Windows...
python build.py

REM 빌드 완료 메시지
echo.
echo Build completed! Check the build\windows directory for the executable.
echo.
pause 