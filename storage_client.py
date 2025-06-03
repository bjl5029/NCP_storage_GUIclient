import requests
import json
import os
from typing import Optional, Dict, List
from datetime import datetime
import time
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.exceptions import InsecureRequestWarning


urllib3.disable_warnings(InsecureRequestWarning)


class NaverArchiveStorageClient:
    """네이버 클라우드 Archive Storage API 클라이언트"""
    
    def __init__(self):
        self.auth_url = "https://kr.archive.ncloudstorage.com:5000"
        self.storage_url = "https://kr.archive.ncloudstorage.com"
        self.token = None
        self.access_key = None
        self.secret_key = None
        self.domain_id = None
        self.project_id = None
        
        self.session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10,
            pool_block=False
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.session.verify = True
        
    def set_credentials(self, access_key, secret_key, domain_id, project_id):
        self.access_key = access_key
        self.secret_key = secret_key
        self.domain_id = domain_id
        self.project_id = project_id
        
    def get_token(self):
        """토큰 생성"""
        headers = {
            'Content-Type': 'application/json'
        }
        
        data = {
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "domain": {"id": self.domain_id},
                            "name": self.access_key,
                            "password": self.secret_key
                        }
                    }
                },
                "scope": {
                    "project": {
                        "id": self.project_id
                    }
                }
            }
        }
        
        try:
            response = self.session.post(
                f"{self.auth_url}/v3/auth/tokens",
                headers=headers,
                data=json.dumps(data),
                timeout=30
            )
            
            print(f"인증 응답 상태 코드: {response.status_code}")
            
            if response.status_code == 201:
                self.token = response.headers.get('X-Subject-Token')
                print(f"토큰 생성 성공")
                return True
            else:
                print(f"토큰 생성 실패: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"토큰 생성 오류: {str(e)}")
            return False
    
    def _make_request(self, method, url, **kwargs):
        """HTTP 요청 실행"""
        if not self.token:
            if not self.get_token():
                raise Exception("인증 토큰을 얻을 수 없습니다")
        
        headers = kwargs.get('headers', {})
        headers.update({
            'X-Auth-Token': self.token
        })
        kwargs['headers'] = headers
        
        try:
            response = self.session.request(method, url, **kwargs)
            return response
        except Exception as e:
            print(f"요청 오류: {str(e)}")
            raise
    
    def get_containers(self):
        """컨테이너 목록 조회"""
        try:
            response = self._make_request('GET', f"{self.storage_url}/v1/AUTH_{self.project_id}?format=json")
            
            print(f"컨테이너 목록 조회 응답 코드: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    containers = response.json()
                    print(f"컨테이너 수: {len(containers)}")
                    return containers
                except json.JSONDecodeError:
                    try:
                        lines = response.text.strip().split('\n')
                        containers = []
                        for line in lines:
                            if line.strip():
                                containers.append({'name': line.strip()})
                        return containers
                    except Exception as e:
                        print(f"응답 파싱 오류: {e}")
                        return []
            elif response.status_code == 204:
                print("컨테이너가 없습니다 (204 No Content)")
                return []
            else:
                print(f"컨테이너 목록 조회 실패: {response.status_code}")
                print(f"응답 내용: {response.text}")
                try:
                    lines = response.text.strip().split('\n')
                    containers = []
                    for line in lines:
                        if line.strip():
                            containers.append({'name': line.strip()})
                    return containers
                except:
                    return []
                
        except Exception as e:
            print(f"컨테이너 목록 조회 오류: {str(e)}")
            return []
            
    def get_objects_in_container_text(self, container_name):
        """컨테이너 내 오브젝트 목록을 텍스트 형태로 조회"""
        try:
            response = self._make_request('GET', f"{self.storage_url}/v1/AUTH_{self.project_id}/{container_name}")
            
            if response.status_code == 200:
                object_list = []
                lines = response.text.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        object_list.append({
                            'name': line,
                            'bytes': 0,
                            'last_modified': '',
                            'content_type': 'application/octet-stream'
                        })
                return object_list
            else:
                print(f"오브젝트 목록 조회 실패: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"오브젝트 목록 조회 오류: {str(e)}")
            return []
    
    def upload_file(self, container_name, object_name, file_path, progress_callback=None):
        """파일 업로드"""
        try:
            print(f"파일 업로드 시작: {file_path} -> {object_name}")
            
            if not os.path.exists(file_path):
                print(f"파일이 존재하지 않음: {file_path}")
                return False
            
            file_size = os.path.getsize(file_path)
            print(f"파일 크기: {self.format_file_size(file_size)}")
            
            chunk_size = 1024 * 1024
            
            uploaded = 0
            last_progress = 0
            
            timeout = max(300, int(file_size / (1024 * 1024)) * 10)
            timeout = min(timeout, 3600)
            
            for attempt in range(3):
                print(f"업로드 시도 {attempt + 1}/3")
                print(f"타임아웃 설정: {timeout}초")
                
                def progress_wrapper(monitor):
                    nonlocal uploaded, last_progress
                    uploaded = monitor.bytes_read
                    if progress_callback:
                        current_progress = int((uploaded / file_size) * 100)
                        if current_progress - last_progress >= 1:
                            progress_callback(current_progress)
                            last_progress = current_progress
                
                try:
                    with open(file_path, 'rb') as f:
                        from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
                        
                        multipart_data = MultipartEncoder(
                            fields={'file': (object_name, f, 'application/octet-stream')}
                        )
                        
                        monitor = MultipartEncoderMonitor(multipart_data, progress_wrapper)
                        
                        response = self._make_request(
                            'PUT',
                            f"{self.storage_url}/v1/AUTH_{self.project_id}/{container_name}/{object_name}",
                            data=monitor,
                            headers={'Content-Type': monitor.content_type},
                            timeout=timeout,
                            stream=False
                        )
                        
                        if response.status_code in [200, 201]:
                            print(f"파일 업로드 성공: {object_name}")
                            if progress_callback:
                                progress_callback(100)
                            return True
                        else:
                            print(f"업로드 실패 (시도 {attempt + 1}): 상태 코드 {response.status_code}")
                            print(f"응답: {response.text}")
                
                except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, 
                        requests.exceptions.Timeout, requests.exceptions.ReadTimeout) as e:
                    print(f"네트워크 오류 (시도 {attempt + 1}): {str(e)}")
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                    else:
                        print(f"최대 재시도 횟수 초과")
                        return False
                
                except Exception as e:
                    print(f"예상치 못한 오류 (시도 {attempt + 1}): {str(e)}")
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                    else:
                        return False
            
            return False
            
        except Exception as e:
            print(f"파일 업로드 전체 오류: {str(e)}")
            return False

    def create_container(self, container_name):
        """컨테이너 생성"""
        try:
            response = self._make_request('PUT', f"{self.storage_url}/v1/AUTH_{self.project_id}/{container_name}")
            
            if response.status_code in [201, 202]:
                print(f"컨테이너 생성 성공: {container_name}")
                return True
            else:
                print(f"컨테이너 생성 실패: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"컨테이너 생성 오류: {str(e)}")
            return False
    
    def download_file(self, container_name, object_name, save_path, progress_callback=None):
        """파일 다운로드"""
        try:
            response = self._make_request('GET', f"{self.storage_url}/v1/AUTH_{self.project_id}/{container_name}/{object_name}", stream=True)
            
            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total_size > 0:
                                progress = int((downloaded / total_size) * 100)
                                progress_callback(progress)
                
                print(f"파일 다운로드 성공: {object_name}")
                return True
            else:
                print(f"파일 다운로드 실패: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"파일 다운로드 오류: {str(e)}")
            return False

    def delete_object(self, container_name, object_name):
        """오브젝트 삭제"""
        try:
            response = self._make_request('DELETE', f"{self.storage_url}/v1/AUTH_{self.project_id}/{container_name}/{object_name}")
            
            if response.status_code == 204:
                print(f"오브젝트 삭제 성공: {object_name}")
                return True
            else:
                print(f"오브젝트 삭제 실패: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"오브젝트 삭제 오류: {str(e)}")
            return False

    def get_objects_with_prefix(self, container_name, prefix=""):
        """특정 prefix로 시작하는 오브젝트 목록 조회 (폴더 구조 지원)"""
        try:
            url_params = "?format=json&delimiter=/"
            if prefix:
                url_params += f"&prefix={prefix}"
            
            url = f"{self.storage_url}/v1/AUTH_{self.project_id}/{container_name}{url_params}"
            print(f"폴더별 오브젝트 목록 조회 URL: {url}")
            print(f"컨테이너명: {container_name}, Prefix: {prefix}")
            
            response = self._make_request('GET', url)
            print(f"응답 상태 코드: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    objects = response.json()
                    print(f"파싱된 오브젝트 목록: {objects}")
                    print(f"오브젝트 개수: {len(objects)}")
                    return objects
                except json.JSONDecodeError as e:
                    print(f"JSON 파싱 오류: {e}")
                    return []
            elif response.status_code == 204:
                print("빈 컨테이너/폴더 (204 No Content)")
                return []
            else:
                print(f"오브젝트 목록 조회 실패: {response.status_code}")
                print(f"응답 내용: {response.text}")
                return []
                
        except Exception as e:
            print(f"오브젝트 목록 조회 오류: {str(e)}")
            return []

    def parse_folder_structure(self, objects, current_prefix=""):
        """오브젝트 목록을 폴더와 파일로 구분하여 파싱"""
        try:
            print(f"parse_folder_structure 호출 - objects: {len(objects)}, current_prefix: '{current_prefix}'")
            
            if not objects:
                print("빈 객체 목록")
                return []
            
            folders = []
            files = []
            seen_items = set()
            
            for i, obj in enumerate(objects):
                try:
                    print(f"처리 중인 객체 [{i+1}/{len(objects)}]: {{'name': '{obj.get('name', 'N/A')}', 'type': '{obj.get('subdir', 'file') if 'subdir' in obj else 'file'}', 'content_type': '{obj.get('content_type', 'N/A')}', 'bytes': {obj.get('bytes', 0)}}}")
                except Exception as e:
                    print(f"객체 정보 로깅 오류: {e}")
                
                if 'subdir' in obj:
                    folder_path = obj['subdir']
                    
                    if not folder_path.startswith(current_prefix):
                        continue
                    
                    relative_path = folder_path[len(current_prefix):]
                    
                    if '/' in relative_path.rstrip('/'):
                        continue
                    
                    folder_name = relative_path.rstrip('/')
                    if folder_name and folder_name not in seen_items:
                        print(f"폴더 추가: {folder_name} -> {folder_path}")
                        folders.append({
                            'name': folder_name,
                            'type': 'folder',
                            'full_path': folder_path,
                            'bytes': 0,
                            'last_modified': '',
                            'content_type': 'application/directory'
                        })
                        seen_items.add(folder_name)
                
                elif obj.get('content_type') == 'application/directory':
                    obj_name = obj.get('name', '')
                    
                    if not obj_name.startswith(current_prefix):
                        continue
                    
                    relative_path = obj_name[len(current_prefix):]
                    
                    if '/' in relative_path:
                        continue
                    
                    if relative_path and relative_path not in seen_items:
                        folder_name = relative_path
                        folder_path = f"{obj_name}/" if not obj_name.endswith('/') else obj_name
                        
                        print(f"폴더 추가: {folder_name} -> {folder_path}")
                        folders.append({
                            'name': folder_name,
                            'type': 'folder',
                            'full_path': folder_path,
                            'bytes': obj.get('bytes', 0),
                            'last_modified': obj.get('last_modified', ''),
                            'content_type': obj.get('content_type', 'application/directory')
                        })
                        seen_items.add(folder_name)
            
            for i, obj in enumerate(objects):
                if 'subdir' in obj:
                    continue
                
                if obj.get('content_type') == 'application/directory':
                    continue
                
                obj_name = obj.get('name', '')
                
                if not obj_name.startswith(current_prefix):
                    continue
                
                relative_path = obj_name[len(current_prefix):]
                
                if '/' in relative_path:
                    continue
                
                if relative_path not in seen_items:
                    print(f"파일 추가: {relative_path} -> {obj_name}")
                    files.append({
                        'name': relative_path,
                        'type': 'file',
                        'full_path': obj_name,
                        'bytes': obj.get('bytes', 0),
                        'last_modified': obj.get('last_modified', ''),
                        'content_type': obj.get('content_type', 'application/octet-stream')
                    })
            
            result = sorted(folders, key=lambda x: x['name'].lower()) + sorted(files, key=lambda x: x['name'].lower())
            
            print(f"최종 결과: {len(result)}개 항목 ({len(folders)}개 폴더, {len(files)}개 파일)")
            return result
            
        except Exception as e:
            print(f"폴더 구조 파싱 오류: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def download_folder(self, container_name, folder_path, local_base_path, progress_callback=None):
        """폴더 다운로드"""
        try:
            all_objects = self.get_all_objects_in_folder(container_name, folder_path)
            
            if not all_objects:
                return True
            
            total_files = len(all_objects)
            completed_files = 0
            
            for obj in all_objects:
                local_path = os.path.join(local_base_path, obj['name'][len(folder_path):])
                
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                success = self.download_file(container_name, obj['name'], local_path)
                if not success:
                    return False
                
                completed_files += 1
                if progress_callback:
                    progress = int((completed_files / total_files) * 100)
                    progress_callback(progress)
            
            return True
            
        except Exception as e:
            print(f"폴더 다운로드 오류: {str(e)}")
            return False

    def get_all_objects_in_folder(self, container_name, folder_path):
        """폴더 내 모든 오브젝트 조회 (재귀적)"""
        try:
            all_objects = []
            response = self._make_request('GET', f"{self.storage_url}/v1/AUTH_{self.project_id}/{container_name}?format=json&prefix={folder_path}")
            
            if response.status_code == 200:
                objects = response.json()
                for obj in objects:
                    if not obj['name'].endswith('/'):
                        all_objects.append(obj)
            
            return all_objects
            
        except Exception as e:
            print(f"폴더 내 오브젝트 조회 오류: {str(e)}")
            return []

    def upload_folder(self, container_name, local_folder_path, remote_base_path, progress_callback=None):
        """폴더 업로드"""
        try:
            print(f"폴더 업로드 시작: {local_folder_path}")
            print(f"원격 기본 경로: {remote_base_path}")
            
            if not os.path.exists(local_folder_path):
                print(f"로컬 폴더가 존재하지 않음: {local_folder_path}")
                return False
            
            all_files = []
            for root, dirs, files in os.walk(local_folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.isfile(file_path):
                        all_files.append(file_path)
            
            if not all_files:
                print("업로드할 파일이 없습니다")
                return True
            
            total_files = len(all_files)
            uploaded_files = 0
            failed_files = []
            
            print(f"업로드할 파일 수: {total_files}")
            total_size = sum(os.path.getsize(f) for f in all_files)
            print(f"총 크기: {self.format_file_size(total_size)}")
            
            for i, file_path in enumerate(all_files):
                try:
                    relative_path = os.path.relpath(file_path, local_folder_path)
                    
                    remote_object_name = f"{remote_base_path}/{relative_path}".replace("\\", "/")
                    
                    print(f"업로드 중 ({i+1}/{total_files}): {relative_path}")
                    
                    def file_progress_callback(file_progress):
                        current_file_contribution = file_progress / total_files
                        completed_files_contribution = (uploaded_files / total_files) * 100
                        total_progress = int(completed_files_contribution + current_file_contribution)
                        if progress_callback:
                            progress_callback(total_progress)
                    
                    success = self.upload_file(
                        container_name, 
                        remote_object_name, 
                        file_path, 
                        file_progress_callback
                    )
                    
                    if success:
                        uploaded_files += 1
                        print(f"업로드 성공: {relative_path}")
                    else:
                        failed_files.append(relative_path)
                        print(f"업로드 실패: {relative_path}")
                        
                except Exception as e:
                    print(f"파일 업로드 중 오류 ({relative_path}): {str(e)}")
                    failed_files.append(relative_path)
            
            if progress_callback:
                progress_callback(100)
            
            success_rate = (uploaded_files / total_files) * 100
            print(f"폴더 업로드 완료: {uploaded_files}/{total_files} 파일 성공 ({success_rate:.1f}%)")
            
            if failed_files:
                print(f"실패한 파일들:")
                for failed_file in failed_files:
                    print(f"  - {failed_file}")
                return False
            
            return True
            
        except Exception as e:
            print(f"폴더 업로드 오류: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def format_file_size(size_bytes):
        """파일 크기를 읽기 쉬운 형태로 변환"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 1)
        return f"{s} {size_names[i]}" 