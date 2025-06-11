# NCP Storage Manager

네이버 클라우드 플랫폼의 다양한 스토리지 서비스를 통합 관리할 수 있는 GUI 애플리케이션입니다.

## 지원 스토리지 서비스

- **Archive Storage**: 장기 보관용 스토리지 (Swift API 기반)
- **Object Storage**: 범용 오브젝트 스토리지 (S3 호환 API)
- **Ncloud Storage**: 네이버 클라우드 전용 스토리지 (S3 호환 API)

## 주요 기능

- 통합된 GUI로 여러 스토리지 서비스 관리
- 파일/폴더 업로드/다운로드
- 대용량 파일 자동 멀티파트 업로드
- 압축 업로드 지원
- 실시간 진행률 표시
- 다크/라이트 테마 자동 감지

## 시스템 요구사항

- Python 3.8 이상
- PyQt6
- 지원 운영체제: Windows 10+, macOS 10.13+, Ubuntu 18.04+

## 빌드 방법

### 1. 공통 준비사항

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

빌드가 완료되면 `build/` 디렉토리에 플랫폼별 폴더가 생성됩니다:

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

## 개발 환경에서 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 애플리케이션 실행
python integrated_storage_gui.py
```

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 문제 해결

### 빌드 실패 시
1. Python 버전 확인 (3.8 이상 필요)
2. 의존성 재설치: `pip install -r requirements.txt --force-reinstall`
3. 빌드 캐시 정리: `python build.py --clean`

### 실행 오류 시
1. 인증 정보 확인
2. 네트워크 연결 확인
3. 방화벽 설정 확인 