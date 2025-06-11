# NCP Storage Manager

NCP의 스토리지 서비스를 관리하는 GUI 애플리케이션.

## 지원 서비스

- **Archive Storage**: (Swift API 기반)
- **Object Storage**: (S3 호환 API)
- **Ncloud Storage**: (S3 호환 API)

## 시스템 요구사항

- Python 3.8 이상
- PyQt6
- 운영체제: Windows 10+, macOS 10.13+, Ubuntu 18.04+(GUI)

## 빌드 방법

```bash
# 저장소 클론 (또는 파일 다운로드)
git clone <repository-url>
cd ncp_storage_gui

# 가상환경 생성 (권장)
python -m venv venv

# 가상환경 활성화
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 2. 플랫폼별 빌드

#### Windows
```batch
# 배치 파일 실행
build_windows.bat

# 또는 수동 빌드
python -m pip install -r requirements.txt
python build.py
```

#### macOS
```bash
# 스크립트 실행
./build_macos.sh

# 또는 수동 빌드
pip install -r requirements.txt
python build.py
```

#### Ubuntu/Linux
```bash
# 스크립트 실행
./build_ubuntu.sh

# 또는 수동 빌드
pip install -r requirements.txt
python build.py
```

### 3. 빌드 결과
```
build/
├── windows/          # Windows 실행 파일
│   └── NCP_Storage_Manager.exe
├── macos/            # macOS 앱 번들
│   └── NCP Storage Manager.app/
└── ubuntu/           # Linux 실행 파일
    └── NCP_Storage_Manager
```

## 설정

첫 실행 시 각 스토리지 서비스의 인증 정보를 입력해야 합니다:

### Archive Storage
- Access Key ID
- Secret Key  
- Domain ID
- Project ID

### Object Storage / Ncloud Storage
- Access Key ID
- Secret Key

설정은 `config.json` 파일에 저장됩니다.

### 빌드 실패 시
1. Python 버전 확인 (>=3.8)
2. 의존성 재설치: `pip install -r requirements.txt --force-reinstall`
3. 빌드 캐시 정리: `python build.py --clean`
