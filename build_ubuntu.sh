#!/bin/bash

echo "NCP Storage Manager - Ubuntu/Linux Build Script"
echo "==============================================="

# 시스템 의존성 확인
echo "Checking system dependencies..."

# Python3와 pip 확인
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed"
    exit 1
fi

if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed"
    exit 1
fi

# 가상환경 활성화 (선택사항)
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# 의존성 설치
echo "Installing dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# 빌드 실행
echo "Building for Ubuntu/Linux..."
python3 build.py

# 빌드 완료 메시지
echo ""
echo "Build completed! Check the build/ubuntu directory for the executable."
echo ""

# 실행 파일 권한 설정
if [ -f "build/ubuntu/NCP_Storage_Manager" ]; then
    chmod +x build/ubuntu/NCP_Storage_Manager
    echo "✓ Executable permissions set"
    echo "  Path: build/ubuntu/NCP_Storage_Manager"
else
    echo "✗ Executable not found"
fi

echo ""
echo "To run the application:"
echo "  ./build/ubuntu/NCP_Storage_Manager" 