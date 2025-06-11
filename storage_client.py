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
import ssl

urllib3.disable_warnings(InsecureRequestWarning)

class NaverArchiveStorageClient:

    def __init__(self):
        self.auth_url = "https://kr.archive.ncloudstorage.com:5000"
        self.storage_url = "https://kr.archive.ncloudstorage.com"
        self.token = None
        self.access_key = None
        self.secret_key = None
        self.domain_id = None
        self.project_id = None

        self.session = requests.Session()

        self.session.verify = True

        retry_strategy = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,
            pool_maxsize=20,
            pool_block=False
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def set_credentials(self, access_key, secret_key, domain_id, project_id):
        self.access_key = access_key
        self.secret_key = secret_key
        self.domain_id = domain_id
        self.project_id = project_id

    def test_connection(self):

        try:
            if not all([self.access_key, self.secret_key, self.domain_id, self.project_id]):
                print("인증 정보가 완전하지 않습니다.")
                return False

            if self.get_token():
                containers = self.get_containers()
                if containers is not None:
                    print(f"Archive Storage 연결 테스트 성공: {len(containers)}개 컨테이너 발견")
                    return True
                else:
                    print("Archive Storage 연결 테스트 실패: 컨테이너 목록 조회 실패")
                    return False
            else:
                print("Archive Storage 연결 테스트 실패: 토큰 생성 실패")
                return False

        except Exception as e:
            print(f"Archive Storage 연결 테스트 오류: {str(e)}")
            return False

    def get_token(self):

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

    def upload_file(self, container_name, object_name, file_path, progress_callback=None):

        try:
            print(f"파일 업로드 시작: {file_path} -> {object_name}")

            if not os.path.exists(file_path):
                print(f"파일이 존재하지 않음: {file_path}")
                return False

            file_size = os.path.getsize(file_path)
            print(f"파일 크기: {self.format_file_size(file_size)}")

            slo_threshold = 5 * 1024 * 1024 * 1024

            if file_size > slo_threshold:
                print(f"대용량 파일 감지: SLO (Static Large Objects) 업로드 사용")
                return self.upload_large_file_slo(container_name, object_name, file_path, progress_callback)
            else:
                return self.upload_small_file_simple(container_name, object_name, file_path, progress_callback)

        except Exception as e:
            print(f"파일 업로드 전체 오류: {str(e)}")
            return False

    def upload_small_file_simple(self, container_name, object_name, file_path, progress_callback=None):

        try:
            file_size = os.path.getsize(file_path)
            timeout = max(300, int(file_size / (1024 * 1024)) * 10)
            timeout = min(timeout, 3600)

            for attempt in range(3):
                print(f"업로드 시도 {attempt + 1}/3")

                try:
                    with open(file_path, 'rb') as f:
                        response = self._make_request(
                            'PUT',
                            f"{self.storage_url}/v1/AUTH_{self.project_id}/{container_name}/{object_name}",
                            data=f,
                            headers={'Content-Type': 'application/octet-stream'},
                            timeout=timeout
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
            print(f"소용량 파일 업로드 오류: {str(e)}")
            return False

    def upload_large_file_slo(self, container_name, object_name, file_path, progress_callback=None):

        try:
            file_size = os.path.getsize(file_path)
            segment_size = 100 * 1024 * 1024

            if segment_size > file_size:
                segment_size = max(file_size // 10, 5 * 1024 * 1024)

            total_segments = (file_size + segment_size - 1) // segment_size
            print(f"SLO 업로드: {total_segments}개 세그먼트, 세그먼트 크기: {self.format_file_size(segment_size)}")

            segment_container = f"{container_name}_segments"
            try:
                self.create_container(segment_container)
            except:
                pass

            uploaded_bytes = 0
            segments_manifest = []

            with open(file_path, 'rb') as f:
                for segment_num in range(total_segments):
                    start_byte = segment_num * segment_size
                    end_byte = min(start_byte + segment_size, file_size)
                    segment_data = f.read(end_byte - start_byte)

                    if not segment_data:
                        break

                    segment_object_name = f"{object_name}/{segment_num:06d}"

                    segment_uploaded = False
                    for attempt in range(3):
                        try:
                            print(f"세그먼트 {segment_num + 1}/{total_segments} 업로드 중... (시도 {attempt + 1}/3)")

                            response = self._make_request(
                                'PUT',
                                f"{self.storage_url}/v1/AUTH_{self.project_id}/{segment_container}/{segment_object_name}",
                                data=segment_data,
                                headers={
                                    'Content-Type': 'application/octet-stream',
                                    'Content-Length': str(len(segment_data))
                                },
                                timeout=600
                            )

                            if response.status_code in [200, 201]:
                                uploaded_bytes += len(segment_data)
                                segment_uploaded = True

                                segments_manifest.append({
                                    "path": f"/{segment_container}/{segment_object_name}",
                                    "etag": response.headers.get('etag', '').strip('"'),
                                    "size_bytes": len(segment_data)
                                })

                                if progress_callback:
                                    progress = int((uploaded_bytes / file_size) * 100)
                                    progress_callback(progress)

                                print(f"세그먼트 {segment_num + 1}/{total_segments} 업로드 완료")
                                break
                            else:
                                print(f"세그먼트 업로드 실패 (시도 {attempt + 1}): {response.status_code}")
                                print(f"응답: {response.text}")
                                if attempt == 2:
                                    raise Exception(f"세그먼트 {segment_num + 1} 업로드 최종 실패")

                        except Exception as e:
                            print(f"세그먼트 {segment_num + 1} 업로드 오류 (시도 {attempt + 1}): {str(e)}")
                            if attempt < 2:
                                time.sleep(2 ** attempt)
                            else:
                                raise

                    if not segment_uploaded:
                        raise Exception(f"세그먼트 {segment_num + 1} 업로드 실패")

            print("모든 세그먼트 업로드 완료. SLO 매니페스트 생성 중...")
            return self.create_slo_manifest(container_name, object_name, segments_manifest)

        except Exception as e:
            print(f"SLO 업로드 오류: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def create_slo_manifest(self, container_name, object_name, segments_manifest):

        try:

            manifest_json = json.dumps(segments_manifest)

            response = self._make_request(
                'PUT',
                f"{self.storage_url}/v1/AUTH_{self.project_id}/{container_name}/{object_name}?multipart-manifest=put",
                data=manifest_json.encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(manifest_json.encode('utf-8')))
                },
                timeout=300
            )

            if response.status_code in [200, 201]:
                print(f"SLO 매니페스트 생성 성공: {object_name}")
                print("대용량 파일 SLO 업로드 완료!")
                return True
            else:
                print(f"SLO 매니페스트 생성 실패: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"SLO 매니페스트 생성 오류: {str(e)}")
            return False

    def delete_slo_object(self, container_name, object_name):

        try:

            response = self._make_request(
                'DELETE',
                f"{self.storage_url}/v1/AUTH_{self.project_id}/{container_name}/{object_name}?multipart-manifest=delete"
            )

            if response.status_code == 204:
                print(f"SLO 객체 완전 삭제 성공: {object_name}")
                return True
            else:
                print(f"SLO 객체 삭제 실패: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"SLO 객체 삭제 오류: {str(e)}")
            return False

    def create_container(self, container_name):

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

    def delete_object(self, container_name, object_name):

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

    def get_containers(self):

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

    def download_file(self, container_name, object_name, save_path, progress_callback=None):

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

    def get_objects_with_prefix(self, container_name, prefix=""):

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

        try:
            if not objects:
                return []

            folders = []
            files = []
            seen_items = set()

            for i, obj in enumerate(objects):
                try:

                    if 'subdir' in obj:
                        folder_name = obj['subdir'].rstrip('/')
                        if folder_name.startswith(current_prefix):
                            relative_folder = folder_name[len(current_prefix):]
                            if '/' not in relative_folder and relative_folder not in seen_items:
                                folders.append({
                                    'name': relative_folder,
                                    'type': 'folder',
                                    'full_path': obj['subdir'],
                                    'bytes': 0,
                                    'last_modified': '',
                                    'content_type': 'application/directory'
                                })
                                seen_items.add(relative_folder)
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
                        files.append({
                            'name': relative_path,
                            'type': 'file',
                            'full_path': obj_name,
                            'bytes': obj.get('bytes', 0),
                            'last_modified': obj.get('last_modified', ''),
                            'content_type': obj.get('content_type', 'application/octet-stream')
                        })
                        seen_items.add(relative_path)

                except Exception as e:
                    continue

            result = sorted(folders, key=lambda x: x['name'].lower()) + sorted(files, key=lambda x: x['name'].lower())

            return result

        except Exception as e:
            print(f"폴더 구조 파싱 오류: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def upload_folder(self, container_name, local_folder_path, remote_base_path, progress_callback=None):

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

        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 1)
        return f"{s} {size_names[i]}"

    def list_objects(self, container_name, prefix="", delimiter="/"):

        try:
            objects = self.get_objects_with_prefix(container_name, prefix)
            parsed_objects = self.parse_folder_structure(objects, prefix)

            result = []
            for obj in parsed_objects:
                result.append({
                    'name': obj['name'],
                    'size': obj.get('bytes', 0),
                    'type': obj['type'],
                    'last_modified': obj.get('last_modified', ''),
                    'key': obj.get('full_path', obj['name'])
                })

            return result

        except Exception as e:
            print(f"객체 목록 조회 오류: {str(e)}")
            return []