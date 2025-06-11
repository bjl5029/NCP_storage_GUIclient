import boto3
import os
import logging
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config
from boto3.s3.transfer import TransferConfig
import threading

class ObjectStorageClient:

    def __init__(self):
        self.access_key = None
        self.secret_key = None
        self.endpoint_url = "https://kr.object.ncloudstorage.com"
        self.region_name = "kr-standard"
        self.s3_client = None
        self.s3_resource = None

        logging.getLogger('boto3').setLevel(logging.WARNING)
        logging.getLogger('botocore').setLevel(logging.WARNING)

    def set_credentials(self, access_key, secret_key):

        self.access_key = access_key
        self.secret_key = secret_key

        config = Config(
            region_name=self.region_name,
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            max_pool_connections=50,
            connect_timeout=60,
            read_timeout=300
        )

        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                config=config
            )

            self.s3_resource = boto3.resource(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                config=config
            )

            print("Object Storage 클라이언트 초기화 완료")
            return True

        except Exception as e:
            print(f"클라이언트 초기화 오류: {str(e)}")
            return False

    def test_connection(self):

        try:
            if not self.s3_client:
                return False

            response = self.s3_client.list_buckets()
            print("연결 테스트 성공")
            return True

        except Exception as e:
            print(f"연결 테스트 실패: {str(e)}")
            return False

    def create_bucket(self, bucket_name):

        try:

            if not self._is_valid_bucket_name(bucket_name):
                print("잘못된 버킷 이름입니다. 소문자, 숫자, 하이픈만 사용할 수 있으며 3-63자여야 합니다.")
                return False

            self.s3_client.create_bucket(Bucket=bucket_name)
            print(f"버킷 생성 성공: {bucket_name}")
            return True

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'BucketAlreadyExists':
                print(f"버킷이 이미 존재합니다: {bucket_name}")
            elif error_code == 'BucketAlreadyOwnedByYou':
                print(f"이미 소유한 버킷입니다: {bucket_name}")
            else:
                print(f"버킷 생성 실패 ({error_code}): {e.response['Error']['Message']}")
            return False
        except Exception as e:
            print(f"버킷 생성 오류: {str(e)}")
            return False

    def get_buckets(self):

        try:
            response = self.s3_client.list_buckets()
            buckets = []

            for bucket in response['Buckets']:
                buckets.append({
                    'name': bucket['Name'],
                    'creation_date': bucket['CreationDate']
                })

            print(f"버킷 목록 조회 성공: {len(buckets)}개")
            return buckets

        except Exception as e:
            print(f"버킷 목록 조회 실패: {str(e)}")
            return []

    def list_objects(self, bucket_name, prefix='', delimiter=''):

        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')

            page_iterator = paginator.paginate(
                Bucket=bucket_name,
                Prefix=prefix,
                Delimiter=delimiter
            )

            objects = []

            for page in page_iterator:

                if 'CommonPrefixes' in page:
                    for prefix_info in page['CommonPrefixes']:
                        folder_name = prefix_info['Prefix'].rstrip('/')
                        if '/' in folder_name:
                            folder_name = folder_name.split('/')[-1]

                        objects.append({
                            'name': folder_name,
                            'size': 0,
                            'type': 'folder',
                            'last_modified': None,
                            'key': prefix_info['Prefix']
                        })

                if 'Contents' in page:
                    for obj in page['Contents']:

                        if obj['Key'].endswith('/'):
                            continue

                        file_name = obj['Key']
                        if prefix and file_name.startswith(prefix):
                            file_name = file_name[len(prefix):]

                        if '/' in file_name:
                            continue

                        objects.append({
                            'name': file_name,
                            'size': obj['Size'],
                            'type': 'file',
                            'last_modified': obj['LastModified'],
                            'key': obj['Key']
                        })

            print(f"객체 목록 조회 성공: {len(objects)}개")
            return objects

        except Exception as e:
            print(f"객체 목록 조회 실패: {str(e)}")
            return []

    def upload_file(self, bucket_name, object_key, file_path, progress_callback=None):

        try:
            if not os.path.exists(file_path):
                print(f"파일이 존재하지 않음: {file_path}")
                return False

            file_size = os.path.getsize(file_path)
            print(f"파일 업로드 시작: {file_path} -> {object_key} ({self.format_file_size(file_size)})")

            class ProgressCallback:
                def __init__(self, callback_func, total_size):
                    self._callback = callback_func
                    self._total_size = total_size
                    self._uploaded = 0
                    self._lock = threading.Lock()

                def __call__(self, bytes_transferred):
                    with self._lock:
                        self._uploaded += bytes_transferred
                        if self._callback and self._total_size > 0:
                            progress = int((self._uploaded / self._total_size) * 100)
                            self._callback(min(progress, 100))

            callback = None
            if progress_callback:
                callback = ProgressCallback(progress_callback, file_size)

            if file_size > 100 * 1024 * 1024:
                print("멀티파트 업로드 사용")
                self.s3_client.upload_file(
                    file_path,
                    bucket_name,
                    object_key,
                    Callback=callback,
                    Config=TransferConfig(
                        multipart_threshold=1024 * 25,
                        max_concurrency=10,
                        multipart_chunksize=1024 * 25,
                        use_threads=True
                    )
                )
            else:
                self.s3_client.upload_file(
                    file_path,
                    bucket_name,
                    object_key,
                    Callback=callback
                )

            print(f"파일 업로드 성공: {object_key}")
            return True

        except ClientError as e:
            print(f"파일 업로드 실패: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            print(f"파일 업로드 오류: {str(e)}")
            return False

    def download_file(self, bucket_name, object_key, local_path, progress_callback=None):

        try:

            try:
                response = self.s3_client.head_object(Bucket=bucket_name, Key=object_key)
                file_size = response['ContentLength']
            except ClientError:
                file_size = 0

            print(f"파일 다운로드 시작: {object_key} -> {local_path} ({self.format_file_size(file_size)})")

            class ProgressCallback:
                def __init__(self, callback_func, total_size):
                    self._callback = callback_func
                    self._total_size = total_size
                    self._downloaded = 0
                    self._lock = threading.Lock()

                def __call__(self, bytes_transferred):
                    with self._lock:
                        self._downloaded += bytes_transferred
                        if self._callback and self._total_size > 0:
                            progress = int((self._downloaded / self._total_size) * 100)
                            self._callback(min(progress, 100))

            callback = None
            if progress_callback:
                callback = ProgressCallback(progress_callback, file_size)

            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            self.s3_client.download_file(
                bucket_name,
                object_key,
                local_path,
                Callback=callback
            )

            print(f"파일 다운로드 성공: {local_path}")
            return True

        except ClientError as e:
            print(f"파일 다운로드 실패: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            print(f"파일 다운로드 오류: {str(e)}")
            return False

    def delete_object(self, bucket_name, object_key):

        try:
            self.s3_client.delete_object(Bucket=bucket_name, Key=object_key)
            print(f"객체 삭제 성공: {object_key}")
            return True

        except ClientError as e:
            print(f"객체 삭제 실패: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            print(f"객체 삭제 오류: {str(e)}")
            return False

    def upload_folder(self, bucket_name, local_folder_path, remote_base_path="", progress_callback=None):
        """폴더를 재귀적으로 업로드"""
        try:
            if not os.path.exists(local_folder_path) or not os.path.isdir(local_folder_path):
                print(f"폴더가 존재하지 않음: {local_folder_path}")
                return False

            files_to_upload = []
            for root, dirs, files in os.walk(local_folder_path):
                for file in files:
                    local_file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(local_file_path, local_folder_path)
                    
                    # 윈도우 경로 구분자를 슬래시로 변경
                    relative_path = relative_path.replace(os.sep, '/')
                    
                    if remote_base_path:
                        remote_key = f"{remote_base_path.rstrip('/')}/{relative_path}"
                    else:
                        remote_key = relative_path
                    
                    files_to_upload.append((local_file_path, remote_key))

            total_files = len(files_to_upload)
            if total_files == 0:
                print("업로드할 파일이 없습니다")
                return True

            print(f"폴더 업로드 시작: {total_files}개 파일")
            
            success_count = 0
            for i, (local_file_path, remote_key) in enumerate(files_to_upload):
                if progress_callback:
                    progress = int((i / total_files) * 100)
                    progress_callback(progress)

                try:
                    if self.upload_file(bucket_name, remote_key, local_file_path):
                        success_count += 1
                        print(f"업로드 성공 ({i+1}/{total_files}): {remote_key}")
                    else:
                        print(f"업로드 실패: {remote_key}")
                except Exception as e:
                    print(f"파일 업로드 실패: {local_file_path} - {str(e)}")
                    continue

            if progress_callback:
                progress_callback(100)

            print(f"폴더 업로드 완료: {success_count}/{total_files} 파일 성공")
            return success_count == total_files

        except Exception as e:
            print(f"폴더 업로드 오류: {str(e)}")
            return False

    def create_folder(self, bucket_name, folder_path):

        try:
            if not folder_path.endswith('/'):
                folder_path += '/'

            self.s3_client.put_object(
                Bucket=bucket_name,
                Key=folder_path,
                Body=b''
            )

            print(f"폴더 생성 성공: {folder_path}")
            return True

        except ClientError as e:
            print(f"폴더 생성 실패: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            print(f"폴더 생성 오류: {str(e)}")
            return False

    def delete_folder(self, bucket_name, folder_prefix):

        try:
            if not folder_prefix.endswith('/'):
                folder_prefix += '/'

            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=folder_prefix)

            delete_count = 0
            for page in page_iterator:
                if 'Contents' in page:
                    objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]

                    if objects_to_delete:
                        self.s3_client.delete_objects(
                            Bucket=bucket_name,
                            Delete={'Objects': objects_to_delete}
                        )
                        delete_count += len(objects_to_delete)

            print(f"폴더 삭제 성공: {folder_prefix} ({delete_count}개 객체)")
            return True

        except ClientError as e:
            print(f"폴더 삭제 실패: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            print(f"폴더 삭제 오류: {str(e)}")
            return False

    def _is_valid_bucket_name(self, bucket_name):

        import re

        if len(bucket_name) < 3 or len(bucket_name) > 63:
            return False

        if not re.match(r'^[a-z0-9\-]+$', bucket_name):
            return False

        if bucket_name.startswith('-') or bucket_name.endswith('-'):
            return False

        return True

    def format_file_size(self, size_bytes):

        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024.0 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1

        return f"{size_bytes:.1f} {size_names[i]}"