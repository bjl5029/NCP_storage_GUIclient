import boto3
import os
import threading
from typing import Optional, Dict, List, Callable
from datetime import datetime
import time
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError
from boto3.s3.transfer import TransferConfig
import logging

class RealNcloudStorageClient:

    def __init__(self):
        self.access_key = None
        self.secret_key = None
        self.region = 'kr'
        self.base_endpoint = 'https://kr.ncloudstorage.com'
        self.client = None
        self.connected = False
        self.current_bucket = None

        logging.getLogger('boto3').setLevel(logging.WARNING)
        logging.getLogger('botocore').setLevel(logging.WARNING)

    def connect(self, access_key, secret_key, endpoint_url=None):

        try:
            self.access_key = access_key
            self.secret_key = secret_key

            if endpoint_url:
                self.base_endpoint = endpoint_url
            else:
                self.base_endpoint = 'https://kr.ncloudstorage.com'

            config = Config(
                signature_version='s3v4',
                retries={'max_attempts': 3, 'mode': 'adaptive'},
                max_pool_connections=50,
                region_name=self.region
            )

            self.client = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                endpoint_url=self.base_endpoint,
                region_name=self.region,
                config=config
            )

            if self.test_connection():
                self.connected = True
                print(f"Ncloud Storage 연결 성공: {self.base_endpoint}")
                return True
            else:
                self.connected = False
                return False

        except Exception as e:
            print(f"Ncloud Storage 연결 실패: {str(e)}")
            self.connected = False
            return False

    def get_bucket_client(self, bucket_name):

        try:
            if not self.access_key or not self.secret_key:
                return None

            bucket_endpoint = f"https://{bucket_name}.kr.ncloudstorage.com"

            config = Config(
                signature_version='s3v4',
                retries={'max_attempts': 3, 'mode': 'adaptive'},
                max_pool_connections=50,
                region_name=self.region
            )

            bucket_client = boto3.client(
                's3',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                endpoint_url=bucket_endpoint,
                region_name=self.region,
                config=config
            )

            return bucket_client

        except Exception as e:
            print(f"버킷 클라이언트 생성 실패 ({bucket_name}): {str(e)}")
            return None

    def disconnect(self):

        self.client = None
        self.connected = False
        self.current_bucket = None
        print("Ncloud Storage 연결이 해제되었습니다.")

    def list_buckets(self):

        if not self.connected:
            return []

        try:
            response = self.client.list_buckets()
            buckets = [bucket['Name'] for bucket in response['Buckets']]
            print(f"버킷 목록 조회 완료: {len(buckets)}개")
            return buckets
        except Exception as e:
            print(f"버킷 목록 조회 실패: {str(e)}")
            return []

    def create_bucket(self, bucket_name):

        if not self.connected:
            return False

        try:

            self.client.create_bucket(Bucket=bucket_name)
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
            print(f"버킷 생성 실패: {str(e)}")
            return False

    def delete_bucket(self, bucket_name):

        if not self.connected:
            return False

        try:
            self.client.delete_bucket(Bucket=bucket_name)
            return True
        except Exception as e:
            print(f"버킷 삭제 실패: {str(e)}")
            return False

    def list_objects(self, bucket_name, prefix='', delimiter=''):

        if not self.connected:
            return []

        try:
            kwargs = {
                'Bucket': bucket_name,
                'MaxKeys': 1000
            }

            if prefix:
                kwargs['Prefix'] = prefix
            if delimiter:
                kwargs['Delimiter'] = delimiter

            response = self.client.list_objects_v2(**kwargs)
            objects = []

            if 'CommonPrefixes' in response:
                for prefix_info in response['CommonPrefixes']:
                    original_prefix = prefix_info['Prefix']
                    folder_name = original_prefix.rstrip('/')
                    if '/' in folder_name:
                        folder_name = folder_name.split('/')[-1]

                    objects.append({
                        'name': folder_name,
                        'size': 0,
                        'type': 'folder',
                        'last_modified': None,
                        'key': original_prefix
                    })

            if 'Contents' in response:
                for obj in response['Contents']:

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
                        'key': obj['Key'],
                        'storage_class': obj.get('StorageClass', 'STANDARD')
                    })

            return objects

        except Exception as e:
            print(f"객체 목록 조회 실패: {str(e)}")
            return []

    def upload_file(self, local_file_path, bucket_name, object_key, progress_callback=None, storage_class='STANDARD'):

        if not self.connected:
            return False

        try:
            file_size = os.path.getsize(local_file_path)

            def upload_callback(bytes_transferred):
                if progress_callback:
                    progress = int((bytes_transferred / file_size) * 100)
                    progress_callback(progress)

            extra_args = {}
            if storage_class in ['STANDARD', 'DEEP_ARCHIVE']:
                extra_args['StorageClass'] = storage_class

            if file_size > 5 * 1024 * 1024 * 1024:
                print(f"대용량 파일 감지 ({self.format_file_size(file_size)}): 멀티파트 업로드 사용")
                config = TransferConfig(
                    multipart_threshold=1024 * 1024 * 100,
                    max_concurrency=10,
                    multipart_chunksize=1024 * 1024 * 100,
                    use_threads=True
                )

                self.client.upload_file(
                    local_file_path,
                    bucket_name,
                    object_key,
                    Config=config,
                    Callback=upload_callback,
                    ExtraArgs=extra_args
                )
            else:

                self.client.upload_file(
                    local_file_path,
                    bucket_name,
                    object_key,
                    Callback=upload_callback,
                    ExtraArgs=extra_args
                )

            return True

        except Exception as e:
            print(f"파일 업로드 오류: {str(e)}")
            return False

    def download_file(self, bucket_name, object_key, local_file_path, progress_callback=None):

        if not self.connected:
            return False

        try:

            try:
                response = self.client.head_object(Bucket=bucket_name, Key=object_key)
                file_size = response['ContentLength']
            except:
                file_size = 0

            def download_callback(bytes_transferred):
                if progress_callback and file_size > 0:
                    progress = int((bytes_transferred / file_size) * 100)
                    progress_callback(progress)

            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

            self.client.download_file(
                bucket_name,
                object_key,
                local_file_path,
                Callback=download_callback
            )

            return True

        except Exception as e:
            print(f"파일 다운로드 오류: {str(e)}")
            return False

    def delete_object(self, bucket_name, object_key):

        if not self.connected:
            return False

        try:
            self.client.delete_object(Bucket=bucket_name, Key=object_key)
            return True

        except Exception as e:
            print(f"객체 삭제 오류: {str(e)}")
            return False

    def create_folder(self, bucket_name, folder_path):

        if not self.connected:
            return False

        try:
            if not folder_path.endswith('/'):
                folder_path += '/'

            self.client.put_object(
                Bucket=bucket_name,
                Key=folder_path,
                Body=b''
            )

            return True

        except Exception as e:
            print(f"폴더 생성 오류: {str(e)}")
            return False

    def test_connection(self):

        try:
            if not self.client:
                return False

            response = self.client.list_buckets()
            print("연결 테스트 성공")
            return True

        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"연결 테스트 실패 - AWS 오류 ({error_code}): {e.response['Error']['Message']}")
            return False
        except NoCredentialsError:
            print("연결 테스트 실패 - 인증 정보 없음")
            return False
        except Exception as e:
            print(f"연결 테스트 실패: {str(e)}")
            return False

    def get_buckets(self):

        try:
            response = self.client.list_buckets()
            buckets = []

            for bucket in response['Buckets']:
                bucket_info = {
                    'name': bucket['Name'],
                    'creation_date': bucket['CreationDate'].strftime('%Y-%m-%d %H:%M:%S')
                }
                buckets.append(bucket_info)

            print(f"버킷 목록 조회 성공: {len(buckets)}개")
            return buckets

        except ClientError as e:
            print(f"버킷 목록 조회 실패: {e.response['Error']['Message']}")
            return []
        except Exception as e:
            print(f"버킷 목록 조회 오류: {str(e)}")
            return []

    def get_objects_in_bucket(self, bucket_name, prefix="", delimiter="/"):

        try:
            paginator = self.client.get_paginator('list_objects_v2')

            page_iterator = paginator.paginate(
                Bucket=bucket_name,
                Prefix=prefix,
                Delimiter=delimiter
            )

            objects = []
            folders = []

            for page in page_iterator:

                if 'CommonPrefixes' in page:
                    for common_prefix in page['CommonPrefixes']:
                        folder_name = common_prefix['Prefix'].rstrip('/')
                        if prefix:
                            folder_display_name = folder_name[len(prefix):]
                        else:
                            folder_display_name = folder_name

                        folders.append({
                            'type': 'folder',
                            'name': folder_display_name,
                            'full_path': common_prefix['Prefix'],
                            'size': 0,
                            'modified': '',
                            'is_folder': True
                        })

                if 'Contents' in page:
                    for obj in page['Contents']:

                        if obj['Key'].endswith('/'):
                            continue

                        object_name = obj['Key']
                        if prefix and object_name.startswith(prefix):
                            display_name = object_name[len(prefix):]
                        else:
                            display_name = object_name

                        if delimiter in display_name:
                            continue

                        objects.append({
                            'type': 'file',
                            'name': display_name,
                            'full_path': object_name,
                            'size': obj['Size'],
                            'modified': obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S'),
                            'is_folder': False
                        })

            folders.sort(key=lambda x: x['name'].lower())
            objects.sort(key=lambda x: x['name'].lower())

            result = folders + objects
            print(f"객체 목록 조회 성공: 폴더 {len(folders)}개, 파일 {len(objects)}개")
            return result

        except ClientError as e:
            print(f"객체 목록 조회 실패: {e.response['Error']['Message']}")
            return []
        except Exception as e:
            print(f"객체 목록 조회 오류: {str(e)}")
            return []

    def upload_folder(self, bucket_name, local_folder_path, remote_base_path="", progress_callback=None):

        try:
            if not os.path.exists(local_folder_path) or not os.path.isdir(local_folder_path):
                print(f"폴더가 존재하지 않음: {local_folder_path}")
                return False

            files_to_upload = []
            for root, dirs, files in os.walk(local_folder_path):
                for file in files:
                    local_file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(local_file_path, local_folder_path)

                    if remote_base_path:
                        remote_path = f"{remote_base_path.rstrip('/')}/{relative_path.replace(os.sep, '/')}"
                    else:
                        remote_path = relative_path.replace(os.sep, '/')

                    files_to_upload.append((local_file_path, remote_path))

            total_files = len(files_to_upload)

            success_count = 0
            for i, (local_file_path, remote_path) in enumerate(files_to_upload):
                if progress_callback:
                    progress = int((i / total_files) * 100)
                    progress_callback(progress)

                try:
                    if self.upload_file(local_file_path, bucket_name, remote_path):
                        success_count += 1
                except Exception as e:
                    print(f"파일 업로드 실패: {local_file_path} - {str(e)}")
                    continue

            if progress_callback:
                progress_callback(100)

            return success_count == total_files

        except Exception as e:
            print(f"폴더 업로드 오류: {str(e)}")
            return False

    def delete_folder(self, bucket_name, folder_prefix):

        try:
            if not folder_prefix.endswith('/'):
                folder_prefix += '/'

            paginator = self.client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=folder_prefix)

            delete_count = 0
            for page in page_iterator:
                if 'Contents' in page:
                    objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]

                    if objects_to_delete:
                        self.client.delete_objects(
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

        pattern = re.compile(r'^[a-z0-9][a-z0-9\-]*[a-z0-9]$')
        return pattern.match(bucket_name) is not None

    @staticmethod
    def format_file_size(size_bytes):

        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024.0 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1

        return f"{size_bytes:.1f} {size_names[i]}"

    def advanced_multipart_upload(self, local_file_path, bucket_name, object_key,
                                 progress_callback=None, storage_class='STANDARD',
                                 chunk_size=100*1024*1024):

        if not self.connected:
            return False

        try:
            file_size = os.path.getsize(local_file_path)

            extra_args = {}
            if storage_class in ['STANDARD', 'DEEP_ARCHIVE']:
                extra_args['StorageClass'] = storage_class

            print(f"멀티파트 업로드 시작: {object_key}")
            response = self.client.create_multipart_upload(
                Bucket=bucket_name,
                Key=object_key,
                **extra_args
            )
            upload_id = response['UploadId']
            print(f"업로드 ID: {upload_id}")

            parts = []
            part_number = 1
            bytes_uploaded = 0

            with open(local_file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break

                    print(f"파트 {part_number} 업로드 중...")
                    part_response = self.client.upload_part(
                        Bucket=bucket_name,
                        Key=object_key,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=chunk
                    )

                    parts.append({
                        'ETag': part_response['ETag'],
                        'PartNumber': part_number
                    })

                    bytes_uploaded += len(chunk)
                    if progress_callback:
                        progress = int((bytes_uploaded / file_size) * 100)
                        progress_callback(progress)

                    part_number += 1

            print("멀티파트 업로드 완료 중...")
            self.client.complete_multipart_upload(
                Bucket=bucket_name,
                Key=object_key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )

            print(f"멀티파트 업로드 성공: {object_key}")
            return True

        except Exception as e:
            print(f"멀티파트 업로드 오류: {str(e)}")

            try:
                if 'upload_id' in locals():
                    self.client.abort_multipart_upload(
                        Bucket=bucket_name,
                        Key=object_key,
                        UploadId=upload_id
                    )
                    print("중단된 멀티파트 업로드 정리 완료")
            except:
                pass
            return False

    def list_multipart_uploads(self, bucket_name):

        if not self.connected:
            return []

        try:
            response = self.client.list_multipart_uploads(Bucket=bucket_name)
            uploads = []

            if 'Uploads' in response:
                for upload in response['Uploads']:
                    uploads.append({
                        'key': upload['Key'],
                        'upload_id': upload['UploadId'],
                        'initiated': upload['Initiated'],
                        'storage_class': upload.get('StorageClass', 'STANDARD')
                    })

            return uploads

        except Exception as e:
            print(f"멀티파트 업로드 목록 조회 오류: {str(e)}")
            return []

    def list_parts(self, bucket_name, object_key, upload_id):

        if not self.connected:
            return []

        try:
            response = self.client.list_parts(
                Bucket=bucket_name,
                Key=object_key,
                UploadId=upload_id
            )

            parts = []
            if 'Parts' in response:
                for part in response['Parts']:
                    parts.append({
                        'part_number': part['PartNumber'],
                        'etag': part['ETag'],
                        'size': part['Size'],
                        'last_modified': part['LastModified']
                    })

            return parts

        except Exception as e:
            print(f"파트 목록 조회 오류: {str(e)}")
            return []

    def abort_multipart_upload(self, bucket_name, object_key, upload_id):

        if not self.connected:
            return False

        try:
            self.client.abort_multipart_upload(
                Bucket=bucket_name,
                Key=object_key,
                UploadId=upload_id
            )
            print(f"멀티파트 업로드 중단 완료: {object_key} (ID: {upload_id})")
            return True

        except Exception as e:
            print(f"멀티파트 업로드 중단 오류: {str(e)}")
            return False