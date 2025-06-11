# NCP_storage_GUIclient

NCP의 여러 Storage를 비개발자가 편리하게 사용할 수 있도록 GUI 프로그램으로 만듦.

## 주의
1. 최대 연결 시간이 1시간으로 설정되어 있음. 매우 큰 파일 또는 폴더 업로드 시 storage.py에서 timeout을 수정할 것.
2. 인증 정보 저장 시 키가 평문으로 저장됨. 배포 시 AWS lambda 등을 이용해 인증 API를 구성하거나, 인증 로직을 Presigned URL으로 변경하기를 권장.
