#!/bin/bash

echo "NCP Storage Manager - macOS Build Script"
echo "========================================"

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
echo "Building for macOS..."
python3 build.py

# 빌드 완료 메시지
echo ""
echo "Build completed! Check the build/macos directory for the application bundle."
echo ""

# .app 번들 생성 확인
if [ -d "build/macos/NCP Storage Manager.app" ]; then
    echo "✓ macOS application bundle created successfully"
    echo "  Path: build/macos/NCP Storage Manager.app"
else
    echo "✗ Application bundle not found"
fi 