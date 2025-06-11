import sys
import os
import json
import zipfile
import tempfile
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                           QWidget, QLabel, QLineEdit, QPushButton, QTextEdit,
                           QFileDialog, QProgressBar, QComboBox, QListWidget,
                           QGroupBox, QGridLayout, QMessageBox,
                           QInputDialog, QListWidgetItem, QTabWidget, QCheckBox,
                           QDialog, QScrollArea)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QPalette

from storage_client import NaverArchiveStorageClient
from object_storage_client import ObjectStorageClient
from ncloud_storage_client import RealNcloudStorageClient

class ConsoleOutput:

    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

    def write(self, text):
        if text.strip():
            self.text_widget.append(text.strip())
            scrollbar = self.text_widget.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            QApplication.processEvents()
        self.original_stdout.write(text)

    def flush(self):
        pass

    def restore(self):
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

class StorageTypeSelectionDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_storage_type = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("스토리지 유형 선택")
        self.setModal(True)
        self.resize(600, 500)

        layout = QVBoxLayout(self)

        title = QLabel("네이버 클라우드 플랫폼 스토리지 GUI Client")
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin: 20px; color: #0078d4;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("사용하실 스토리지 서비스를 선택해주세요")
        subtitle.setStyleSheet("font-size: 14px; margin: 10px; color: #666666;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addWidget(QLabel())

        options_layout = QVBoxLayout()

        archive_btn = self.create_storage_option_button(
            "Archive Storage",
            "",
            "",
            'archive'
        )
        options_layout.addWidget(archive_btn)

        object_btn = self.create_storage_option_button(
            "Object Storage",
            "",
            "",
            'object'
        )
        options_layout.addWidget(object_btn)

        ncloud_btn = self.create_storage_option_button(
            "Ncloud Storage",
            "",
            "",
            'ncloud'
        )
        options_layout.addWidget(ncloud_btn)

        layout.addLayout(options_layout)

        layout.addStretch()

        self.apply_dialog_theme()

    def is_dark_mode(self):

        palette = self.palette()
        bg_color = palette.color(QPalette.ColorRole.Window)
        brightness = (bg_color.red() + bg_color.green() + bg_color.blue()) / 3
        return brightness < 128

    def apply_dialog_theme(self):

        if self.is_dark_mode():
            self.setStyleSheet("QDialog { background-color: #2b2b2b; color: #ffffff; }")
        else:
            self.setStyleSheet("QDialog { background-color: #ffffff; color: #000000; }")

    def create_storage_option_button(self, title, subtitle, description, storage_type):

        container = QWidget()

        if not subtitle.strip() and not description.strip():
            container.setFixedHeight(60)
        else:
            container.setFixedHeight(120)
        container.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(5)

        title_label = QLabel(title)
        layout.addWidget(title_label)

        if subtitle.strip():
            subtitle_label = QLabel(subtitle)
            layout.addWidget(subtitle_label)

        if description.strip():
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        layout.addStretch()

        if self.is_dark_mode():
            title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
            if subtitle.strip():
                subtitle_label.setStyleSheet("font-size: 12px; color: #cccccc;")
            if description.strip():
                desc_label.setStyleSheet("font-size: 11px; color: #999999;")

            container.setStyleSheet("QWidget { background-color: #404040; border: 1px solid #555555; border-radius: 8px; margin: 5px; } QWidget:hover { background-color: #505050; border-color: #666666; }")
        else:
            title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #000000;")
            if subtitle.strip():
                subtitle_label.setStyleSheet("font-size: 12px; color: #333333;")
            if description.strip():
                desc_label.setStyleSheet("font-size: 11px; color: #666666;")

            container.setStyleSheet("QWidget { background-color: #f0f0f0; border: 1px solid #cccccc; border-radius: 8px; margin: 5px; } QWidget:hover { background-color: #e0e0e0; border-color: #bbbbbb; }")

        def mousePressEvent(event):
            self.select_storage_type(storage_type)

        container.mousePressEvent = mousePressEvent

        return container

    def select_storage_type(self, storage_type):

        self.selected_storage_type = storage_type
        self.accept()



class StorageConnectionDialog(QDialog):

    def __init__(self, storage_type, parent=None):
        super().__init__(parent)
        self.storage_type = storage_type
        self.result_data = None
        self.init_ui()
        self.load_saved_config()

    def init_ui(self):
        self.setWindowTitle(f"{self.get_storage_name()} 연결 설정")
        self.setModal(True)
        self.resize(500, 400)

        layout = QVBoxLayout(self)

        title = QLabel(f"{self.get_storage_name()} 연결")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)

        form_group = QGroupBox()  # 제목 제거
        form_layout = QGridLayout(form_group)

        if self.storage_type == 'archive':
            self.setup_archive_fields(form_layout)
        elif self.storage_type == 'object':
            self.setup_object_fields(form_layout)
        else:
            self.setup_ncloud_fields(form_layout)

        layout.addWidget(form_group)

        self.add_help_text(layout)

        button_layout = QHBoxLayout()

        # 연결 버튼 (파란색)
        connect_btn = QPushButton("연결")
        connect_btn.clicked.connect(self.test_connection)
        connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """)
        button_layout.addWidget(connect_btn)

        # 취소 버튼 (회색)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #9E9E9E;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #757575;
            }
            QPushButton:pressed {
                background-color: #424242;
            }
        """)
        button_layout.addWidget(cancel_btn)

        # 저장 버튼 (초록색)
        save_btn = QPushButton("저장")
        save_btn.clicked.connect(self.save_config)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
            QPushButton:pressed {
                background-color: #2E7D32;
            }
        """)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def get_storage_name(self):
        names = {
            'archive': 'Archive Storage',
            'object': 'Object Storage',
            'ncloud': 'Ncloud Storage'
        }
        return names.get(self.storage_type, 'Storage')

    def setup_archive_fields(self, layout):
        layout.addWidget(QLabel("Access Key ID:"), 0, 0)
        self.access_key_edit = QLineEdit()
        layout.addWidget(self.access_key_edit, 0, 1)

        layout.addWidget(QLabel("Secret Key:"), 1, 0)
        self.secret_key_edit = QLineEdit()
        self.secret_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.secret_key_edit, 1, 1)

        layout.addWidget(QLabel("Domain ID:"), 2, 0)
        self.domain_id_edit = QLineEdit()
        layout.addWidget(self.domain_id_edit, 2, 1)

        layout.addWidget(QLabel("Project ID:"), 3, 0)
        self.project_id_edit = QLineEdit()
        layout.addWidget(self.project_id_edit, 3, 1)

    def setup_object_fields(self, layout):
        layout.addWidget(QLabel("Access Key:"), 0, 0)
        self.access_key_edit = QLineEdit()
        layout.addWidget(self.access_key_edit, 0, 1)

        layout.addWidget(QLabel("Secret Key:"), 1, 0)
        self.secret_key_edit = QLineEdit()
        self.secret_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.secret_key_edit, 1, 1)

    def setup_ncloud_fields(self, layout):
        region_info = QLabel("리전: kr")
        region_info.setStyleSheet("font-weight: bold; color: #0078d4;")
        layout.addWidget(region_info, 0, 0, 1, 2)

        layout.addWidget(QLabel("Access Key:"), 1, 0)
        self.access_key_edit = QLineEdit()
        layout.addWidget(self.access_key_edit, 1, 1)

        layout.addWidget(QLabel("Secret Key:"), 2, 0)
        self.secret_key_edit = QLineEdit()
        self.secret_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.secret_key_edit, 2, 1)

    def add_help_text(self, layout):
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setMaximumHeight(150)

        if self.storage_type == 'archive':
            content = "<b>Archive Storage 인증 안내</b><br/>담당자에게 전달받은 인증 정보를 입력하세요."
        elif self.storage_type == 'object':
            content = "<b>Object Storage 인증 안내</b><br/>담당자에게 전달받은 인증 정보를 입력하세요."
        else:
            content = "<b>Ncloud Storage 인증 안내</b><br/>담당자에게 전달받은 인증 정보를 입력하세요."

        help_text.setHtml(content)
        layout.addWidget(help_text)

    def load_saved_config(self):
        """통합 config.json 파일에서 스토리지 유형별 설정 로드"""
        try:
            config_file = 'config.json'
            
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    all_config = json.load(f)
                
                # 스토리지 유형별 설정 가져오기
                storage_config = all_config.get(self.storage_type, {})
                
                if self.storage_type == 'archive':
                    self.access_key_edit.setText(storage_config.get('access_key_id', ''))
                    self.secret_key_edit.setText(storage_config.get('secret_key', ''))
                    self.domain_id_edit.setText(storage_config.get('domain_id', ''))
                    self.project_id_edit.setText(storage_config.get('project_id', ''))
                else:
                    self.access_key_edit.setText(storage_config.get('access_key', ''))
                    self.secret_key_edit.setText(storage_config.get('secret_key', ''))
                    
        except Exception as e:
            print(f"설정 로드 오류: {str(e)}")

    def save_config(self):
        """통합 config.json 파일에 스토리지 유형별 설정 저장"""
        try:
            config_file = 'config.json'
            
            # 기존 설정 파일이 있으면 로드, 없으면 빈 딕셔너리 생성
            all_config = {}
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    all_config = json.load(f)
            
            # 현재 스토리지 타입의 설정 업데이트
            if self.storage_type == 'archive':
                all_config[self.storage_type] = {
                    'access_key_id': self.access_key_edit.text(),
                    'secret_key': self.secret_key_edit.text(),
                    'domain_id': self.domain_id_edit.text(),
                    'project_id': self.project_id_edit.text()
                }
            else:
                all_config[self.storage_type] = {
                    'access_key': self.access_key_edit.text(),
                    'secret_key': self.secret_key_edit.text()
                }
            
            # 통합 설정 파일에 저장
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(all_config, f, indent=2, ensure_ascii=False)

            QMessageBox.information(self, "성공", "설정이 저장되었습니다.")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"설정 저장 실패: {str(e)}")

    def test_connection(self):

        try:
            if self.storage_type == 'archive':
                if not all([self.access_key_edit.text(), self.secret_key_edit.text(),
                           self.domain_id_edit.text(), self.project_id_edit.text()]):
                    QMessageBox.warning(self, "경고", "모든 필드를 입력해주세요.")
                    return

                client = NaverArchiveStorageClient()
                client.set_credentials(
                    self.access_key_edit.text(),
                    self.secret_key_edit.text(),
                    self.domain_id_edit.text(),
                    self.project_id_edit.text()
                )

                if client.test_connection():
                    self.result_data = {
                        'client': client,
                        'access_key_id': self.access_key_edit.text(),
                        'secret_key': self.secret_key_edit.text(),
                        'domain_id': self.domain_id_edit.text(),
                        'project_id': self.project_id_edit.text()
                    }
                    QMessageBox.information(self, "성공", "연결에 성공했습니다!")
                    self.accept()
                else:
                    QMessageBox.critical(self, "실패", "연결에 실패했습니다.")

            else:
                if not all([self.access_key_edit.text(), self.secret_key_edit.text()]):
                    QMessageBox.warning(self, "경고", "Access Key와 Secret Key를 입력해주세요.")
                    return

                if self.storage_type == 'object':
                    client = ObjectStorageClient()
                    success = client.set_credentials(self.access_key_edit.text(), self.secret_key_edit.text())
                    if success:
                        success = client.test_connection()
                else:
                    client = RealNcloudStorageClient()
                    success = client.connect(self.access_key_edit.text(), self.secret_key_edit.text())

                if success:
                    self.result_data = {
                        'client': client,
                        'access_key': self.access_key_edit.text(),
                        'secret_key': self.secret_key_edit.text()
                    }
                    QMessageBox.information(self, "성공", "연결에 성공했습니다!")
                    self.accept()
                else:
                    QMessageBox.critical(self, "실패", "연결에 실패했습니다.")

        except Exception as e:
            QMessageBox.critical(self, "오류", f"연결 중 오류: {str(e)}")

class StorageWorkerThread(QThread):

    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, client, operation, *args, **kwargs):
        super().__init__()
        self.client = client
        self.operation = operation
        self.args = args
        self.kwargs = kwargs

        self.storage_type = self._detect_storage_type()

    def _detect_storage_type(self):

        client_name = self.client.__class__.__name__
        if 'Archive' in client_name:
            return 'archive'
        elif 'Object' in client_name:
            return 'object'
        elif 'Ncloud' in client_name:
            return 'ncloud'
        else:
            return 'unknown'

    def run(self):
        try:
            if self.operation == 'upload_file':
                success = self._handle_upload_file()
            elif self.operation == 'download_file':
                success = self._handle_download_file()
            elif self.operation == 'upload_folder':
                success = self._handle_upload_folder()
            else:
                success = False

            message = f"{self.operation} 완료" if success else f"{self.operation} 실패"
            self.finished.emit(success, message)
        except Exception as e:
            self.finished.emit(False, f"{self.operation} 오류: {str(e)}")

    def _handle_upload_file(self):

        if self.storage_type == 'archive':

            container_name, object_name, file_path = self.args
            return self.client.upload_file(
                container_name, object_name, file_path,
                progress_callback=self.progress.emit
            )
        else:

            container_name, object_name, file_path = self.args

            storage_class = self.kwargs.get('storage_class', 'STANDARD')

            if self.storage_type == 'ncloud' and storage_class:
                return self.client.upload_file(
                    file_path, container_name, object_name,
                    progress_callback=self.progress.emit,
                    storage_class=storage_class
                )
            else:
                return self.client.upload_file(
                    file_path, container_name, object_name,
                    progress_callback=self.progress.emit
                )

    def _handle_download_file(self):

        container_name, object_name, local_path = self.args
        return self.client.download_file(
            container_name, object_name, local_path,
            progress_callback=self.progress.emit
        )

    def _handle_upload_folder(self):
        """폴더 업로드를 처리하는 메서드 - 자연스러운 폴더 구조를 유지"""
        container_name, folder_path, remote_path = self.args
        
        # remote_path가 폴더명을 포함하도록 설정되어 있으므로,
        # 실제 업로드 시에는 이 경로를 prefix로 사용
        if self.storage_type == 'archive':
            return self.client.upload_folder(
                container_name, folder_path, remote_path,
                progress_callback=self.progress.emit
            )
        else:
            return self.client.upload_folder(
                container_name, folder_path, remote_path,
                progress_callback=self.progress.emit
            )

class CompressedUploadThread(QThread):

    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    status = pyqtSignal(str)

    def __init__(self, client, storage_type, container_or_bucket, file_paths, folders, current_path, zip_filename, storage_class=None):
        super().__init__()
        self.client = client
        self.storage_type = storage_type
        self.container_or_bucket = container_or_bucket
        self.file_paths = file_paths if file_paths else []
        self.folders = folders if folders else []
        self.current_path = current_path
        self.zip_filename = zip_filename
        self.storage_class = storage_class
        self.temp_zip_path = None

    def run(self):
        try:
            print(f"압축 시작: {len(self.file_paths)}개 파일, {len(self.folders)}개 폴더")

            self.status.emit("압축 파일 생성 중...")
            self.progress.emit(5)

            temp_dir = tempfile.mkdtemp()
            self.temp_zip_path = os.path.join(temp_dir, self.zip_filename)

            with zipfile.ZipFile(self.temp_zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
                for file_path in self.file_paths:
                    if os.path.exists(file_path):
                        arc_name = os.path.basename(file_path)
                        zipf.write(file_path, arc_name)

                for folder_path in self.folders:
                    if os.path.exists(folder_path):
                        folder_name = os.path.basename(folder_path)
                        for root, dirs, files in os.walk(folder_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                relative_path = os.path.relpath(file_path, folder_path)
                                arc_name = os.path.join(folder_name, relative_path)
                                zipf.write(file_path, arc_name)

            zip_size = os.path.getsize(self.temp_zip_path)
            size_str = CompressedUploadThread.format_file_size(zip_size)
            print(f"압축 완료: {self.zip_filename} ({size_str})")

            self.status.emit(f"압축 파일 업로드 시작...")
            self.progress.emit(10)

            if self.current_path:
                remote_path = f"{self.current_path}{self.zip_filename}"
            else:
                remote_path = self.zip_filename

            def upload_progress_callback(progress):
                final_progress = 10 + int(progress * 0.9)
                self.progress.emit(final_progress)

            print(f"압축 파일 업로드 시작: {self.zip_filename}")

            if self.storage_type == 'archive':
                success = self.client.upload_file(
                    self.container_or_bucket,
                    remote_path,
                    self.temp_zip_path,
                    upload_progress_callback
                )
            else:
                if self.storage_type == 'ncloud' and self.storage_class:
                    success = self.client.upload_file(
                        self.temp_zip_path,
                        self.container_or_bucket,
                        remote_path,
                        upload_progress_callback,
                        storage_class=self.storage_class
                    )
                else:
                    success = self.client.upload_file(
                        self.temp_zip_path,
                        self.container_or_bucket,
                        remote_path,
                        upload_progress_callback
                    )

            try:
                os.remove(self.temp_zip_path)
                os.rmdir(temp_dir)
            except:
                pass

            if success:
                message = f"압축 업로드 완료: {self.zip_filename} ({size_str})"
                print("압축 파일 업로드 성공")
                self.finished.emit(True, message)
            else:
                print("압축 파일 업로드 실패")
                self.finished.emit(False, "압축 업로드에 실패했습니다.")

        except Exception as e:

            try:
                if self.temp_zip_path and os.path.exists(self.temp_zip_path):
                    os.remove(self.temp_zip_path)
                if temp_dir and os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
            except:
                pass

            error_msg = f"압축 업로드 오류: {str(e)}"
            print(f"압축 업로드 오류: {str(e)}")
            import traceback
            traceback.print_exc()
            self.finished.emit(False, error_msg)

    @staticmethod
    def format_file_size(size_bytes):
        """파일 크기를 사람이 읽기 쉬운 형태로 변환"""
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024.0 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1

        return f"{size_bytes:.1f} {size_names[i]}"

class MultiFileUploadThread(QThread):

    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, client, storage_type, container_or_bucket, file_paths, current_path, storage_class=None):
        super().__init__()
        self.client = client
        self.storage_type = storage_type
        self.container_or_bucket = container_or_bucket
        self.file_paths = file_paths
        self.current_path = current_path
        self.storage_class = storage_class

    def run(self):
        try:
            total_files = len(self.file_paths)
            uploaded_files = 0
            failed_files = []

            print(f"여러 파일 업로드 시작: {total_files}개 파일")

            for i, file_path in enumerate(self.file_paths):
                if not os.path.exists(file_path):
                    failed_files.append(os.path.basename(file_path))
                    continue

                file_name = os.path.basename(file_path)

                if self.current_path:
                    remote_path = f"{self.current_path}{file_name}"
                else:
                    remote_path = file_name

                def file_progress_callback(file_progress):
                    overall_progress = int(((i + file_progress / 100) / total_files) * 100)
                    self.progress.emit(overall_progress)

                try:

                    if self.storage_type == 'archive':
                        success = self.client.upload_file(
                            self.container_or_bucket,
                            remote_path,
                            file_path,
                            file_progress_callback
                        )
                    else:
                        if self.storage_type == 'ncloud' and self.storage_class:
                            success = self.client.upload_file(
                                file_path,
                                self.container_or_bucket,
                                remote_path,
                                file_progress_callback,
                                storage_class=self.storage_class
                            )
                        else:
                            success = self.client.upload_file(
                                file_path,
                                self.container_or_bucket,
                                remote_path,
                                file_progress_callback
                            )

                    if success:
                        uploaded_files += 1
                    else:
                        failed_files.append(file_name)

                except Exception as e:
                    print(f"파일 업로드 실패: {file_name} - {str(e)}")
                    failed_files.append(file_name)

            if uploaded_files == total_files:
                message = f"모든 파일 업로드 완료 ({uploaded_files}/{total_files})"
                print(f"여러 파일 업로드 성공: {uploaded_files}개")
                self.finished.emit(True, message)
            elif uploaded_files > 0:
                message = f"일부 파일 업로드 완료 ({uploaded_files}/{total_files})\n실패: {', '.join(failed_files)}"
                print(f"여러 파일 업로드 부분 성공: {uploaded_files}/{total_files}")
                self.finished.emit(False, message)
            else:
                message = f"모든 파일 업로드 실패\n실패: {', '.join(failed_files)}"
                print("여러 파일 업로드 전체 실패")
                self.finished.emit(False, message)

        except Exception as e:
            error_msg = f"여러 파일 업로드 오류: {str(e)}"
            print(f"여러 파일 업로드 오류: {str(e)}")
            self.finished.emit(False, error_msg)


class IntegratedStorageGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.archive_client = None
        self.object_client = None
        self.ncloud_client = None

        self.current_storage_type = None

        self.storage_states = {
            'archive': {
                'current_container': None,
                'current_path': '',
                'connected': False
            },
            'object': {
                'current_bucket': None,
                'current_path': '',
                'connected': False
            },
            'ncloud': {
                'current_bucket': None,
                'current_path': '',
                'connected': False
            }
        }

        self.init_ui()
        self.apply_styles()
        self.setup_message_box_styles()

        self.theme_timer = QTimer()
        self.theme_timer.timeout.connect(self.check_theme_change)
        self.theme_timer.start(1000)
        self.last_dark_mode = self.is_dark_mode()

        self.select_initial_storage_type()

    def init_ui(self):

        self.setWindowTitle("네이버 클라우드 통합 Storage GUI Client")
        self.setGeometry(100, 100, 1400, 900)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        self.connection_status_label = QLabel("연결되지 않음")
        self.connection_status_label.setStyleSheet("color: #888888; font-weight: bold; padding: 5px;")
        self.connection_status_label.setMaximumHeight(25)
        main_layout.addWidget(self.connection_status_label)

        self.main_tab_widget = QTabWidget()

        self.archive_tab = QWidget()
        self.main_tab_widget.addTab(self.archive_tab, "Archive Storage")

        self.object_tab = QWidget()
        self.main_tab_widget.addTab(self.object_tab, "Object Storage")

        self.ncloud_tab = QWidget()
        self.main_tab_widget.addTab(self.ncloud_tab, "Ncloud Storage")

        self.init_archive_tab()
        self.init_object_tab()
        self.init_ncloud_tab()

        self.init_console_area(main_widget, main_layout)

        self.main_tab_widget.currentChanged.connect(self.on_storage_type_changed)

        self.console_output = ConsoleOutput(self.console_text)
        sys.stdout = self.console_output
        sys.stderr = self.console_output

        print("네이버 클라우드 통합 Storage GUI가 시작되었습니다.")

    def select_initial_storage_type(self):

        type_dialog = StorageTypeSelectionDialog(self)
        if type_dialog.exec() == QDialog.DialogCode.Accepted and type_dialog.selected_storage_type:
            self.current_storage_type = type_dialog.selected_storage_type

            storage_types = ['archive', 'object', 'ncloud']
            tab_index = storage_types.index(self.current_storage_type)
            self.main_tab_widget.setCurrentIndex(tab_index)

            self.show_connection_dialog()
        else:
            # 사용자가 스토리지 타입 선택을 취소한 경우 완전 종료
            QApplication.quit()
            self.close()

    def show_connection_dialog(self):

        if not self.current_storage_type:
            return

        dialog = StorageConnectionDialog(self.current_storage_type, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_data:
            self.setup_client(dialog.result_data)
        else:

            print(f"{self.get_storage_display_name()} 연결이 취소되었습니다.")

    def setup_client(self, client_data):

        if self.current_storage_type == 'archive':
            self.archive_client = client_data['client']
            self.storage_states['archive']['connected'] = True
            self.refresh_containers()
        elif self.current_storage_type == 'object':
            self.object_client = client_data['client']
            self.storage_states['object']['connected'] = True
            self.refresh_buckets()
        else:
            self.ncloud_client = client_data['client']
            self.storage_states['ncloud']['connected'] = True
            self.refresh_buckets()

        print(f"{self.get_storage_display_name()}에 성공적으로 연결되었습니다.")
        self.update_connection_status()

    def update_connection_status(self):

        if self.current_storage_type and self.storage_states[self.current_storage_type]['connected']:
            status_text = f"연결됨: {self.get_storage_display_name()}"
            self.connection_status_label.setText(status_text)
            self.connection_status_label.setStyleSheet("color: #4CAF50; font-weight: bold; padding: 5px;")
        else:
            self.connection_status_label.setText("연결되지 않음")
            self.connection_status_label.setStyleSheet("color: #888888; font-weight: bold; padding: 5px;")

    def on_storage_type_changed(self, index):

        storage_types = ['archive', 'object', 'ncloud']
        new_type = storage_types[index]
        previous_type = self.current_storage_type

        if self.current_storage_type is None:
            self.current_storage_type = new_type
            return

        if new_type != self.current_storage_type:
            self.current_storage_type = new_type
            print(f"{self.get_storage_display_name()}로 전환")

            if not self.storage_states[new_type]['connected']:

                dialog = StorageConnectionDialog(self.current_storage_type, self)
                if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_data:
                    self.setup_client(dialog.result_data)
                else:

                    if previous_type:
                        previous_index = storage_types.index(previous_type)
                        self.main_tab_widget.setCurrentIndex(previous_index)
                        self.current_storage_type = previous_type
                        print(f"연결 취소로 인해 {self.get_storage_display_name()}로 되돌아갑니다.")
                    return

        if self.current_storage_type:
            self.update_connection_status()

    def get_storage_display_name(self):

        names = {
            'archive': 'Archive Storage',
            'object': 'Object Storage',
            'ncloud': 'Ncloud Storage'
        }
        return names.get(self.current_storage_type, 'Storage')

    def init_archive_tab(self):

        layout = QVBoxLayout(self.archive_tab)

        container_group = QGroupBox()  # 제목 제거
        container_layout = QGridLayout(container_group)

        container_layout.addWidget(QLabel("컨테이너:"), 0, 0)
        self.archive_container_combo = QComboBox()
        self.archive_container_combo.currentTextChanged.connect(self.on_container_changed)
        container_layout.addWidget(self.archive_container_combo, 0, 1, 1, 2)

        refresh_btn = QPushButton("새로고침")
        refresh_btn.clicked.connect(self.refresh_containers)
        container_layout.addWidget(refresh_btn, 0, 3)

        create_btn = QPushButton("컨테이너 생성")
        create_btn.clicked.connect(self.create_container)
        container_layout.addWidget(create_btn, 0, 4)

        layout.addWidget(container_group)

        self.init_file_management_ui(layout, 'archive')

        container_group.setEnabled(False)
        self.archive_container_group = container_group

    def init_object_tab(self):

        layout = QVBoxLayout(self.object_tab)

        bucket_group = QGroupBox()  # 제목 제거
        bucket_layout = QGridLayout(bucket_group)

        bucket_layout.addWidget(QLabel("버킷:"), 0, 0)
        self.object_bucket_combo = QComboBox()
        self.object_bucket_combo.currentTextChanged.connect(self.on_bucket_changed)
        bucket_layout.addWidget(self.object_bucket_combo, 0, 1, 1, 2)

        refresh_btn = QPushButton("새로고침")
        refresh_btn.clicked.connect(self.refresh_buckets)
        bucket_layout.addWidget(refresh_btn, 0, 3)

        create_btn = QPushButton("버킷 생성")
        create_btn.clicked.connect(self.create_bucket)
        bucket_layout.addWidget(create_btn, 0, 4)

        layout.addWidget(bucket_group)

        self.init_file_management_ui(layout, 'object')

        bucket_group.setEnabled(False)
        self.object_bucket_group = bucket_group

    def init_ncloud_tab(self):

        layout = QVBoxLayout(self.ncloud_tab)

        bucket_group = QGroupBox()  # 제목 제거
        bucket_layout = QGridLayout(bucket_group)

        bucket_layout.addWidget(QLabel("버킷:"), 0, 0)
        self.ncloud_bucket_combo = QComboBox()
        self.ncloud_bucket_combo.currentTextChanged.connect(self.on_bucket_changed)
        bucket_layout.addWidget(self.ncloud_bucket_combo, 0, 1, 1, 2)

        refresh_btn = QPushButton("새로고침")
        refresh_btn.clicked.connect(self.refresh_buckets)
        bucket_layout.addWidget(refresh_btn, 0, 3)

        create_btn = QPushButton("버킷 생성")
        create_btn.clicked.connect(self.create_bucket)
        bucket_layout.addWidget(create_btn, 0, 4)

        layout.addWidget(bucket_group)

        self.init_file_management_ui(layout, 'ncloud')

        bucket_group.setEnabled(False)
        self.ncloud_bucket_group = bucket_group

    def init_file_management_ui(self, layout, storage_type):

        file_group = QGroupBox()  # 제목 제거
        file_layout = QVBoxLayout(file_group)

        nav_layout = QHBoxLayout()

        back_btn = QPushButton("← 뒤로")
        back_btn.clicked.connect(lambda: self.go_back())
        back_btn.setEnabled(False)
        back_btn.setFixedWidth(80)
        nav_layout.addWidget(back_btn)

        path_label = QLabel("경로: /")
        path_label.setStyleSheet("font-weight: bold; padding: 5px;")
        nav_layout.addWidget(path_label)

        nav_layout.addStretch()

        new_folder_btn = QPushButton("새 폴더")
        new_folder_btn.clicked.connect(self.create_folder)
        new_folder_btn.setFixedWidth(100)
        nav_layout.addWidget(new_folder_btn)

        file_layout.addLayout(nav_layout)

        # 전체 선택/해제 체크박스 추가
        select_all_layout = QHBoxLayout()
        select_all_checkbox = QCheckBox("전체 선택/해제")
        select_all_checkbox.clicked.connect(lambda checked: self.toggle_all_selection(checked))
        select_all_layout.addWidget(select_all_checkbox)
        select_all_layout.addStretch()
        file_layout.addLayout(select_all_layout)

        files_list = QListWidget()
        files_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        files_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)  # 하이라이트 선택 비활성화 (체크박스만 사용)
        files_list.setMinimumHeight(200)
        file_layout.addWidget(files_list)

        action_layout = QHBoxLayout()

        upload_file_btn = QPushButton("파일 업로드")
        upload_file_btn.clicked.connect(self.upload_files)
        action_layout.addWidget(upload_file_btn)

        upload_folder_btn = QPushButton("폴더 업로드")
        upload_folder_btn.clicked.connect(self.upload_folder)
        action_layout.addWidget(upload_folder_btn)

        download_btn = QPushButton("선택 항목 다운로드")
        download_btn.clicked.connect(self.download_selected)
        action_layout.addWidget(download_btn)

        delete_btn = QPushButton("선택 항목 삭제")
        delete_btn.clicked.connect(self.delete_selected)
        action_layout.addWidget(delete_btn)

        # NCloud Storage에만 Storage Class 변경 버튼 추가
        if storage_type == 'ncloud':
            convert_storage_class_btn = QPushButton("선택 파일 Storage Class 변경")
            convert_storage_class_btn.clicked.connect(self.convert_storage_class)
            action_layout.addWidget(convert_storage_class_btn)

        action_layout.addStretch()

        refresh_btn = QPushButton("새로고침")
        refresh_btn.clicked.connect(self.refresh_files)
        refresh_btn.setFixedWidth(100)
        action_layout.addWidget(refresh_btn)

        file_layout.addLayout(action_layout)

        progress_group = QGroupBox()  # 제목 제거
        progress_layout = QVBoxLayout(progress_group)

        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        progress_layout.addWidget(progress_bar)

        # 상태와 취소 버튼을 한 줄에 배치
        status_layout = QHBoxLayout()
        status_label = QLabel("대기 중")
        status_layout.addWidget(status_label)
        
        status_layout.addStretch()
        
        # 취소 버튼 추가
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.cancel_operation)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 60px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
            QPushButton:pressed {
                background-color: #B71C1C;
            }
        """)
        cancel_btn.setVisible(False)  # 기본적으로 숨김
        status_layout.addWidget(cancel_btn)
        
        progress_layout.addLayout(status_layout)

        file_layout.addWidget(progress_group)

        layout.addWidget(file_group)

        if storage_type == 'archive':
            self.archive_back_btn = back_btn
            self.archive_path_label = path_label
            self.archive_files_list = files_list
            self.archive_file_group = file_group
            self.archive_progress_bar = progress_bar
            self.archive_progress_status_label = status_label
            self.archive_select_all_checkbox = select_all_checkbox
            self.archive_cancel_btn = cancel_btn
        elif storage_type == 'object':
            self.object_back_btn = back_btn
            self.object_path_label = path_label
            self.object_files_list = files_list
            self.object_file_group = file_group
            self.object_progress_bar = progress_bar
            self.object_progress_status_label = status_label
            self.object_select_all_checkbox = select_all_checkbox
            self.object_cancel_btn = cancel_btn
        else:
            self.ncloud_back_btn = back_btn
            self.ncloud_path_label = path_label
            self.ncloud_files_list = files_list
            self.ncloud_file_group = file_group
            self.ncloud_progress_bar = progress_bar
            self.ncloud_progress_status_label = status_label
            self.ncloud_select_all_checkbox = select_all_checkbox
            self.ncloud_cancel_btn = cancel_btn

        file_group.setEnabled(False)

    def toggle_all_selection(self, checked):
        """전체 선택/해제 기능"""
        files_list = None
        if self.current_storage_type == 'archive':
            files_list = self.archive_files_list
        elif self.current_storage_type == 'object':
            files_list = self.object_files_list
        else:
            files_list = self.ncloud_files_list
            
        if files_list:
            for i in range(files_list.count()):
                item = files_list.item(i)
                # 체크박스 상태 변경
                if checked:
                    item.setCheckState(Qt.CheckState.Checked)
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)

    def get_current_client(self):

        if not self.current_storage_type:
            return None

        if self.current_storage_type == 'archive':
            return self.archive_client
        elif self.current_storage_type == 'object':
            return self.object_client
        else:
            return self.ncloud_client

    def get_current_container_or_bucket(self):

        if not self.current_storage_type:
            return None

        if self.current_storage_type == 'archive':
            return self.storage_states['archive']['current_container']
        else:
            state_key = 'current_bucket'
            return self.storage_states[self.current_storage_type][state_key]

    def refresh_containers(self):

        if not self.archive_client:
            return

        try:
            self.archive_container_combo.clear()
            containers = self.archive_client.get_containers()
            for container in containers:
                self.archive_container_combo.addItem(container['name'])

            self.archive_container_group.setEnabled(True)

        except Exception as e:
            print(f"컨테이너 목록 새로고침 오류: {str(e)}")

    def refresh_buckets(self):

        client = self.get_current_client()
        if not client:
            return

        try:
            if self.current_storage_type == 'object':
                combo = self.object_bucket_combo
                group = self.object_bucket_group
            else:
                combo = self.ncloud_bucket_combo
                group = self.ncloud_bucket_group

            combo.clear()
            buckets = client.get_buckets()
            for bucket in buckets:
                combo.addItem(bucket['name'])

            group.setEnabled(True)

        except Exception as e:
            print(f"버킷 목록 새로고침 오류: {str(e)}")

    def on_container_changed(self, container_name):

        if container_name and self.current_storage_type == 'archive':
            self.storage_states['archive']['current_container'] = container_name
            self.storage_states['archive']['current_path'] = ''
            self.archive_file_group.setEnabled(True)
            self.refresh_files()

    def on_bucket_changed(self, bucket_name):

        if bucket_name:
            self.storage_states[self.current_storage_type]['current_bucket'] = bucket_name
            self.storage_states[self.current_storage_type]['current_path'] = ''

            if self.current_storage_type == 'object':
                self.object_file_group.setEnabled(True)
            else:
                self.ncloud_file_group.setEnabled(True)

            self.refresh_files()

    def create_container(self):

        if not self.archive_client:
            return

        name, ok = QInputDialog.getText(self, "컨테이너 생성", "컨테이너 이름:")
        if ok and name.strip():
            if self.archive_client.create_container(name.strip()):
                QMessageBox.information(self, "성공", f"컨테이너 '{name}'이 생성되었습니다.")
                self.refresh_containers()
            else:
                QMessageBox.critical(self, "실패", "컨테이너 생성에 실패했습니다.")

    def create_bucket(self):

        client = self.get_current_client()
        if not client:
            return

        name, ok = QInputDialog.getText(self, "버킷 생성", "버킷 이름:")
        if ok and name.strip():
            if client.create_bucket(name.strip()):
                QMessageBox.information(self, "성공", f"버킷 '{name}'이 생성되었습니다.")
                self.refresh_buckets()
            else:
                QMessageBox.critical(self, "실패", "버킷 생성에 실패했습니다.")

    def refresh_files(self):

        if not self.current_storage_type:
            return

        client = self.get_current_client()
        container_or_bucket = self.get_current_container_or_bucket()

        if not client or not container_or_bucket:
            return

        try:

            if self.current_storage_type == 'archive':
                files_list = self.archive_files_list
                path = self.storage_states['archive']['current_path']

                objects = client.get_objects_with_prefix(container_or_bucket, path)
                items = client.parse_folder_structure(objects, path)
            else:
                if self.current_storage_type == 'object':
                    files_list = self.object_files_list
                else:
                    files_list = self.ncloud_files_list

                path = self.storage_states[self.current_storage_type]['current_path']

                items = client.list_objects(container_or_bucket, prefix=path, delimiter='/')

            files_list.clear()

            for item in items:
                list_item = QListWidgetItem()

                icon = "📁" if item['type'] == 'folder' else "📄"
                display_text = f"{icon} {item['name']}"

                if item['type'] == 'file' and item.get('size', 0) > 0:
                    size_text = CompressedUploadThread.format_file_size(item['size'])
                    display_text += f" ({size_text})"
                    
                    # NCloud Storage에서만 Storage Class 정보 표시
                    if self.current_storage_type == 'ncloud' and 'storage_class' in item:
                        storage_class = item['storage_class']
                        if storage_class == 'STANDARD':
                            display_text += " [일반]"
                        elif storage_class == 'DEEP_ARCHIVE':
                            display_text += " [아카이브]"
                        else:
                            display_text += f" [{storage_class}]"

                list_item.setText(display_text)
                list_item.setData(Qt.ItemDataRole.UserRole, item)

                list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                list_item.setCheckState(Qt.CheckState.Unchecked)

                files_list.addItem(list_item)

            self.update_path_display()

        except Exception as e:
            print(f"파일 목록 새로고침 오류: {str(e)}")

    def update_path_display(self):

        if not self.current_storage_type:
            return

        container_or_bucket = self.get_current_container_or_bucket()
        path = self.storage_states[self.current_storage_type]['current_path']

        if self.current_storage_type == 'archive':
            display = f"컨테이너: {container_or_bucket}"
            label = self.archive_path_label
            back_btn = self.archive_back_btn
        elif self.current_storage_type == 'object':
            display = f"버킷: {container_or_bucket}"
            label = self.object_path_label
            back_btn = self.object_back_btn
        else:
            display = f"버킷: {container_or_bucket}"
            label = self.ncloud_path_label
            back_btn = self.ncloud_back_btn

        if path:
            display += f" / {path}"

        label.setText(f"경로: {display}")
        back_btn.setEnabled(bool(path))

    def on_item_double_clicked(self, item):

        if not self.current_storage_type:
            return

        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data or item_data['type'] != 'folder':
            return

        current_path = self.storage_states[self.current_storage_type]['current_path']
        new_path = f"{current_path}{item_data['name']}/"
        self.storage_states[self.current_storage_type]['current_path'] = new_path

        self.refresh_files()

    def go_back(self):

        if not self.current_storage_type:
            return

        current_path = self.storage_states[self.current_storage_type]['current_path']
        if not current_path:
            return

        if current_path.endswith('/'):
            current_path = current_path[:-1]

        parent_path = '/'.join(current_path.split('/')[:-1])
        if parent_path:
            parent_path += '/'
        else:
            parent_path = ''

        self.storage_states[self.current_storage_type]['current_path'] = parent_path
        self.refresh_files()

    def create_folder(self):

        client = self.get_current_client()
        container_or_bucket = self.get_current_container_or_bucket()

        if not client or not container_or_bucket:
            return

        name, ok = QInputDialog.getText(self, "폴더 생성", "폴더 이름:")
        if not ok or not name.strip():
            return

        try:
            path = self.storage_states[self.current_storage_type]['current_path']
            folder_path = f"{path}{name.strip()}/"

            if self.current_storage_type == 'archive':

                success = client.upload_file(container_or_bucket, f"{folder_path}.foldermarker", "")
            else:

                success = client.create_folder(container_or_bucket, folder_path)

            if success:
                QMessageBox.information(self, "성공", f"폴더 '{name}'이 생성되었습니다.")
                self.refresh_files()
            else:
                QMessageBox.critical(self, "실패", "폴더 생성에 실패했습니다.")

        except Exception as e:
            QMessageBox.critical(self, "오류", f"폴더 생성 중 오류: {str(e)}")

    def upload_files(self):

        try:

            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "업로드할 파일 선택",
                "",
                "모든 파일 (*)"
            )
            if not file_paths:
                return

            client = self.get_current_client()
            container_or_bucket = self.get_current_container_or_bucket()
            path = self.storage_states[self.current_storage_type]['current_path']

            if not client or not container_or_bucket:
                QMessageBox.warning(self, "경고", "스토리지에 연결되지 않았거나 컨테이너/버킷이 선택되지 않았습니다.")
                return

            if len(file_paths) == 1:
                self._upload_single_file(file_paths[0])
                return

            self._upload_multiple_files(file_paths)

        except Exception as e:
            print(f"파일 업로드 대화상자 오류: {str(e)}")
            QMessageBox.critical(self, "오류", f"파일 선택 중 오류가 발생했습니다: {str(e)}")

    def upload_folder(self):

        try:

            folder_path = QFileDialog.getExistingDirectory(
                self,
                "업로드할 폴더 선택",
                "",
                QFileDialog.Option.ShowDirsOnly
            )
            if not folder_path:
                return

            client = self.get_current_client()
            container_or_bucket = self.get_current_container_or_bucket()
            current_path = self.storage_states[self.current_storage_type]['current_path']

            if not client or not container_or_bucket:
                QMessageBox.warning(self, "경고", "스토리지에 연결되지 않았거나 컨테이너/버킷이 선택되지 않았습니다.")
                return

            folder_name = os.path.basename(folder_path)

            total_files = 0
            total_size = 0
            for root, dirs, files in os.walk(folder_path):
                total_files += len(files)
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):
                        total_size += os.path.getsize(file_path)

            if total_files == 0:
                QMessageBox.information(self, "알림", "폴더에 업로드할 파일이 없습니다.")
                return

            size_str = CompressedUploadThread.format_file_size(total_size)

            should_recommend_compression = total_files >= 10 or total_size >= 500 * 1024 * 1024

            if should_recommend_compression:
                # 업로드될 최종 경로 계산
                if current_path:
                    final_location = f"{container_or_bucket}/{current_path}{folder_name}/"
                else:
                    final_location = f"{container_or_bucket}/{folder_name}/"
                    
                reply = self.show_yes_no_cancel_question(
                    "폴더 업로드 방식 선택",
                    f"폴더 '{folder_name}'을 업로드합니다.\n"
                    f"파일 수: {total_files}개\n"
                    f"총 크기: {size_str}\n"
                    f"업로드 위치: {final_location}\n\n"
                    f"파일 수가 많거나 크기가 큰 경우 압축하여 업로드하는 것이 더 빠를 수 있습니다.\n\n"
                    f"압축하여 업로드하시겠습니까?"
                )

                if reply == "cancel":
                    return
                elif reply == "yes":
                    self._upload_files_compressed([], [folder_path])
                    return

            try:

                self.show_progress()
                self.set_status(f"폴더 업로드 중: {folder_name}")

                print(f"폴더 업로드 시작: {folder_name} ({total_files}개 파일, {size_str})")

                # 폴더명을 포함한 원격 경로 설정 (자연스러운 폴더 구조)
                folder_name = os.path.basename(folder_path)
                if current_path:
                    remote_path = f"{current_path}{folder_name}/"
                else:
                    remote_path = f"{folder_name}/"
                
                print(f"업로드 대상 경로: {remote_path}")
                print(f"로컬 폴더: {folder_path}")
                print(f"컨테이너/버킷: {container_or_bucket}")

                self.folder_upload_thread = StorageWorkerThread(
                    client, 'upload_folder',
                    container_or_bucket, folder_path, remote_path
                )
                self.folder_upload_thread.progress.connect(self.update_progress)
                self.folder_upload_thread.finished.connect(self.on_folder_upload_finished)
                self.folder_upload_thread.start()

            except Exception as e:
                self.hide_progress()
                self.set_status("오류")
                QMessageBox.critical(self, "오류", f"폴더 업로드 중 오류: {str(e)}")

        except Exception as e:
            print(f"폴더 업로드 대화상자 오류: {str(e)}")
            QMessageBox.critical(self, "오류", f"폴더 선택 중 오류가 발생했습니다: {str(e)}")

    def _upload_single_file(self, file_path):

        client = self.get_current_client()
        container_or_bucket = self.get_current_container_or_bucket()
        path = self.storage_states[self.current_storage_type]['current_path']

        if not client or not container_or_bucket:
            return

        try:
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            size_str = CompressedUploadThread.format_file_size(file_size)

            self.show_progress()
            self.set_status(f"파일 업로드 중: {file_name}")

            if file_size > 5 * 1024 * 1024 * 1024:
                if not self.show_yes_no_question(
                    "대용량 파일 업로드",
                    f"대용량 파일이 감지되었습니다.\n"
                    f"파일: {file_name}\n"
                    f"크기: {size_str}\n\n"
                    f"멀티파트 업로드를 사용하여 안전하고 효율적으로 업로드하시겠습니까?"
                ):
                    self.hide_progress()
                    self.set_status("대기 중")
                    return

            object_key = f"{path}{file_name}"

            print(f"파일 업로드 시작: {file_name} ({size_str})")

            storage_class = None
            if self.current_storage_type == 'ncloud':
                storage_class = self.get_storage_class_for_upload()
                if storage_class is None:  # 사용자가 취소한 경우
                    self.hide_progress()
                    self.set_status("대기 중")
                    return
                print(f"Storage Class: {storage_class}")

            self.upload_thread = StorageWorkerThread(
                client, 'upload_file',
                container_or_bucket, object_key, file_path,
                storage_class=storage_class
            )
            self.upload_thread.progress.connect(self.update_progress)
            self.upload_thread.finished.connect(self.on_upload_finished)
            self.upload_thread.start()

        except Exception as e:
            self.hide_progress()
            self.set_status("오류")
            QMessageBox.critical(self, "오류", f"파일 업로드 준비 중 오류: {str(e)}")

    def _upload_multiple_files(self, file_paths):

        total_files = len(file_paths)
        total_size = sum(os.path.getsize(fp) for fp in file_paths if os.path.exists(fp))

        file_list = "\n".join([f"• {os.path.basename(fp)}" for fp in file_paths[:10]])
        if total_files > 10:
            file_list += f"\n... 및 {total_files - 10}개 추가 파일"

        size_str = CompressedUploadThread.format_file_size(total_size)

        should_recommend_compression = total_files >= 5 or total_size >= 100 * 1024 * 1024

        if should_recommend_compression:
            reply = self.show_yes_no_cancel_question(
                "업로드 방식 선택",
                f"다음 {total_files}개 파일을 업로드합니다.\n"
                f"총 크기: {size_str}\n"
                f"업로드 위치: {self.get_current_container_or_bucket()}/{self.storage_states[self.current_storage_type]['current_path']}\n\n"
                f"파일 수가 많거나 크기가 큰 경우 압축하여 업로드하는 것이 더 빠르고 안정적입니다.\n\n"
                f"압축하여 업로드하시겠습니까?\n\n"
                f"파일 목록:\n{file_list}"
            )

            if reply == "cancel":
                return
            elif reply == "yes":
                self._upload_files_compressed(file_paths, [])
                return
        else:
            if not self.show_yes_no_question(
                "여러 파일 업로드 확인",
                f"다음 {total_files}개 파일을 업로드하시겠습니까?\n"
                f"총 크기: {size_str}\n"
                f"업로드 위치: {self.get_current_container_or_bucket()}/{self.storage_states[self.current_storage_type]['current_path']}\n\n"
                f"파일 목록:\n{file_list}"
            ):
                return

        # NCloud Storage에서 Storage Class 선택
        storage_class = None
        if self.current_storage_type == 'ncloud':
            storage_class = self.get_storage_class_for_upload()
            if storage_class is None:  # 사용자가 취소한 경우
                return

        client = self.get_current_client()
        container_or_bucket = self.get_current_container_or_bucket()
        path = self.storage_states[self.current_storage_type]['current_path']

        self.show_progress()
        self.set_status(f"여러 파일 업로드 중 ({total_files}개 파일)")

        self.multi_upload_thread = MultiFileUploadThread(
            client,
            self.current_storage_type,
            container_or_bucket,
            file_paths,
            path,
            storage_class
        )
        self.multi_upload_thread.progress.connect(self.update_progress)
        self.multi_upload_thread.finished.connect(self.on_multi_upload_finished)
        self.multi_upload_thread.start()

    def _upload_files_compressed(self, file_paths, folder_paths):

        # NCloud Storage에서 Storage Class 선택
        storage_class = None
        if self.current_storage_type == 'ncloud':
            storage_class = self.get_storage_class_for_upload()
            if storage_class is None:  # 사용자가 취소한 경우
                return

        default_name = "compressed_files.zip"
        if folder_paths and len(folder_paths) == 1:
            folder_name = os.path.basename(folder_paths[0])
            default_name = f"{folder_name}.zip"
        elif file_paths and len(file_paths) > 1:
            default_name = f"files_{len(file_paths)}개.zip"

        zip_filename, ok = QInputDialog.getText(
            self, "압축 파일명 입력",
            "압축 파일명을 입력하세요:\n"
            "(.zip 확장자는 자동으로 추가됩니다)",
            text=default_name.replace('.zip', '')
        )

        if not ok or not zip_filename.strip():
            return

        zip_filename = zip_filename.strip()
        if not zip_filename.lower().endswith('.zip'):
            zip_filename += '.zip'

        client = self.get_current_client()
        container_or_bucket = self.get_current_container_or_bucket()
        path = self.storage_states[self.current_storage_type]['current_path']

        self.show_progress()
        self.set_status(f"압축 파일 생성 중: {zip_filename}")

        self.compressed_upload_thread = CompressedUploadThread(
            client,
            self.current_storage_type,
            container_or_bucket,
            file_paths,
            folder_paths,
            path,
            zip_filename,
            storage_class
        )

        self.compressed_upload_thread.progress.connect(self.update_progress)
        self.compressed_upload_thread.status.connect(self.update_status)
        self.compressed_upload_thread.finished.connect(self.on_compressed_upload_finished)
        self.compressed_upload_thread.start()

    def update_progress(self, value):

        if not self.current_storage_type:
            return

        if self.current_storage_type == 'archive':
            progress_bar = self.archive_progress_bar
        elif self.current_storage_type == 'object':
            progress_bar = self.object_progress_bar
        else:
            progress_bar = self.ncloud_progress_bar

        progress_bar.setValue(value)
        progress_bar.setVisible(True)

        if value >= 100:
            QTimer.singleShot(2000, lambda: progress_bar.setVisible(False))

    def update_status(self, status):

        if not self.current_storage_type:
            return

        if self.current_storage_type == 'archive':
            status_label = self.archive_progress_status_label
        elif self.current_storage_type == 'object':
            status_label = self.object_progress_status_label
        else:
            status_label = self.ncloud_progress_status_label

        status_label.setText(status)

    def show_progress(self):
        """진행률 표시"""
        if self.current_storage_type == 'archive':
            progress_bar = self.archive_progress_bar
            cancel_btn = self.archive_cancel_btn
        elif self.current_storage_type == 'object':
            progress_bar = self.object_progress_bar
            cancel_btn = self.object_cancel_btn
        else:
            progress_bar = self.ncloud_progress_bar
            cancel_btn = self.ncloud_cancel_btn

        if progress_bar:
            progress_bar.setVisible(True)
            progress_bar.setValue(0)
        if cancel_btn:
            cancel_btn.setVisible(True)

    def hide_progress(self):
        """진행률 숨김"""
        if self.current_storage_type == 'archive':
            progress_bar = self.archive_progress_bar
            cancel_btn = self.archive_cancel_btn
        elif self.current_storage_type == 'object':
            progress_bar = self.object_progress_bar
            cancel_btn = self.object_cancel_btn
        else:
            progress_bar = self.ncloud_progress_bar
            cancel_btn = self.ncloud_cancel_btn

        if progress_bar:
            progress_bar.setVisible(False)
            progress_bar.setValue(0)
        if cancel_btn:
            cancel_btn.setVisible(False)

    def cancel_operation(self):
        """현재 진행 중인 작업 취소"""
        try:
            # 현재 실행 중인 워커 스레드 종료
            if hasattr(self, 'current_worker') and self.current_worker:
                if self.current_worker.isRunning():
                    self.current_worker.terminate()
                    self.current_worker.wait(3000)  # 3초 대기
                    if self.current_worker.isRunning():
                        self.current_worker.quit()
                        self.current_worker.wait()
                self.current_worker = None
            
            # 압축 업로드 스레드 종료
            if hasattr(self, 'compressed_upload_thread') and self.compressed_upload_thread:
                if self.compressed_upload_thread.isRunning():
                    self.compressed_upload_thread.terminate()
                    self.compressed_upload_thread.wait(3000)
                    if self.compressed_upload_thread.isRunning():
                        self.compressed_upload_thread.quit()
                        self.compressed_upload_thread.wait()
                self.compressed_upload_thread = None
            
            # 다중 파일 업로드 스레드 종료
            if hasattr(self, 'multi_upload_thread') and self.multi_upload_thread:
                if self.multi_upload_thread.isRunning():
                    self.multi_upload_thread.terminate()
                    self.multi_upload_thread.wait(3000)
                    if self.multi_upload_thread.isRunning():
                        self.multi_upload_thread.quit()
                        self.multi_upload_thread.wait()
                self.multi_upload_thread = None
            
            # UI 상태 초기화
            self.hide_progress()
            self.set_status("작업이 취소되었습니다.")
            
            print("사용자에 의해 작업이 취소되었습니다.")
            
        except Exception as e:
            print(f"작업 취소 중 오류 발생: {str(e)}")
            self.set_status("취소 중 오류가 발생했습니다.")

    def set_status(self, status):

        if not self.current_storage_type:
            return

        if self.current_storage_type == 'archive':
            status_label = self.archive_progress_status_label
        elif self.current_storage_type == 'object':
            status_label = self.object_progress_status_label
        else:
            status_label = self.ncloud_progress_status_label

        status_label.setText(status)

    def on_upload_finished(self, success, message):

        self.update_progress(100)
        self.set_status("완료" if success else "실패")

        if success:
            print("파일 업로드 성공")
            self.refresh_files()
            QMessageBox.information(self, "업로드 완료", message)
        else:
            print("파일 업로드 실패")
            QMessageBox.critical(self, "업로드 실패", message)

        QTimer.singleShot(3000, lambda: (self.hide_progress(), self.set_status("대기 중")))

    def on_multi_upload_finished(self, success, message):

        self.update_progress(100)
        self.set_status("완료" if success else "실패")

        if success:
            print("여러 파일 업로드 성공")
            self.refresh_files()
            QMessageBox.information(self, "업로드 완료", message)
        else:
            print("여러 파일 업로드 부분 실패")
            QMessageBox.warning(self, "업로드 부분 실패", message)

        QTimer.singleShot(3000, lambda: (self.hide_progress(), self.set_status("대기 중")))

    def on_compressed_upload_finished(self, success, message):

        self.update_progress(100)
        self.set_status("완료" if success else "실패")

        if success:
            print("압축 파일 업로드 성공")
            self.refresh_files()
            QMessageBox.information(self, "압축 업로드 완료", message)
        else:
            print("압축 파일 업로드 실패")
            QMessageBox.critical(self, "압축 업로드 실패", message)

        QTimer.singleShot(3000, lambda: (self.hide_progress(), self.set_status("대기 중")))

    def on_folder_upload_finished(self, success, message):

        self.update_progress(100)
        self.set_status("완료" if success else "실패")

        if success:
            print("폴더 업로드 성공")
            self.refresh_files()
            QMessageBox.information(self, "업로드 완료", message)
        else:
            print("폴더 업로드 실패")
            QMessageBox.critical(self, "업로드 실패", message)

        QTimer.singleShot(3000, lambda: (self.hide_progress(), self.set_status("대기 중")))

    def download_selected(self):

        selected_items = self.get_selected_items()
        if not selected_items:
            QMessageBox.information(self, "알림", "다운로드할 항목을 선택해주세요.")
            return

        download_dir = QFileDialog.getExistingDirectory(self, "다운로드 폴더 선택")
        if not download_dir:
            return

        client = self.get_current_client()
        container_or_bucket = self.get_current_container_or_bucket()

        success_count = 0
        for item in selected_items:
            if item['type'] == 'file':
                try:
                    local_path = os.path.join(download_dir, item['name'])
                    success = client.download_file(container_or_bucket, item['key'], local_path)
                    if success:
                        success_count += 1
                except Exception as e:
                    print(f"다운로드 실패 ({item['name']}): {str(e)}")

        if success_count > 0:
            print(f"{success_count}개 파일 다운로드 완료")
            QMessageBox.information(self, "완료", f"{success_count}개 파일이 다운로드되었습니다.")
        else:
            print("다운로드 실패")
            QMessageBox.critical(self, "실패", "다운로드에 실패했습니다.")

    def delete_selected(self):

        selected_items = self.get_selected_items()
        if not selected_items:
            QMessageBox.information(self, "알림", "삭제할 항목을 선택해주세요.")
            return

        if not self.show_yes_no_question(
            "삭제 확인",
            f"선택된 {len(selected_items)}개 항목을 삭제하시겠습니까?\n\n이 작업은 되돌릴 수 없습니다."
        ):
            return

        client = self.get_current_client()
        container_or_bucket = self.get_current_container_or_bucket()

        success_count = 0
        for item in selected_items:
            try:
                if item['type'] == 'file':
                    success = client.delete_object(container_or_bucket, item['key'])
                else:
                    if hasattr(client, 'delete_folder'):
                        success = client.delete_folder(container_or_bucket, item['key'])
                    else:
                        success = True

                if success:
                    success_count += 1

            except Exception as e:
                print(f"삭제 실패 ({item['name']}): {str(e)}")

        if success_count > 0:
            print(f"{success_count}개 항목 삭제 완료")
            QMessageBox.information(self, "완료", f"{success_count}개 항목이 삭제되었습니다.")
            self.refresh_files()
        else:
            print("삭제 실패")
            QMessageBox.critical(self, "실패", "삭제에 실패했습니다.")

    def get_selected_items(self):

        if not self.current_storage_type:
            return []

        if self.current_storage_type == 'archive':
            files_list = self.archive_files_list
        elif self.current_storage_type == 'object':
            files_list = self.object_files_list
        else:
            files_list = self.ncloud_files_list

        selected_items = []
        for i in range(files_list.count()):
            item = files_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                item_data = item.data(Qt.ItemDataRole.UserRole)
                if item_data:
                    selected_items.append(item_data)

        return selected_items

    def init_console_area(self, main_widget, main_layout):

        main_layout.addWidget(self.main_tab_widget, 1)

        console_group = QGroupBox()  # 제목 제거
        console_layout = QVBoxLayout(console_group)

        self.console_text = QTextEdit()
        self.console_text.setReadOnly(True)
        self.console_text.setMaximumHeight(100)
        self.console_text.setObjectName("console_text")

        console_layout.addWidget(self.console_text)

        console_btn_layout = QHBoxLayout()
        clear_btn = QPushButton("콘솔 지우기")
        clear_btn.clicked.connect(lambda: self.console_text.clear())
        clear_btn.setFixedWidth(80)
        console_btn_layout.addWidget(clear_btn)
        console_btn_layout.addStretch()
        console_layout.addLayout(console_btn_layout)

        main_layout.addWidget(console_group)

    def is_dark_mode(self):

        palette = self.palette()
        bg_color = palette.color(QPalette.ColorRole.Window)
        brightness = (bg_color.red() + bg_color.green() + bg_color.blue()) / 3
        return brightness < 128

    def apply_styles(self):

        if self.is_dark_mode():
            self.apply_dark_theme()
        else:
            self.apply_light_theme()

    def apply_dark_theme(self):

        self.setStyleSheet("QMainWindow { background-color: #2b2b2b; color: #ffffff; }")

    def apply_light_theme(self):

        self.setStyleSheet("QMainWindow { background-color: #ffffff; color: #000000; }")

    def setup_message_box_styles(self):
        """MessageBox 버튼 스타일 설정"""
        self.setStyleSheet(self.styleSheet() + """
            QMessageBox QPushButton {
                min-width: 80px;
                min-height: 30px;
                border-radius: 5px;
                font-weight: bold;
            }
            QMessageBox QPushButton[text="예"] {
                background-color: #2196F3;
                color: white;
                border: 2px solid #1976D2;
            }
            QMessageBox QPushButton[text="예"]:hover {
                background-color: #1976D2;
            }
            QMessageBox QPushButton[text="아니오"] {
                background-color: #F44336;
                color: white;
                border: 2px solid #D32F2F;
            }
            QMessageBox QPushButton[text="아니오"]:hover {
                background-color: #D32F2F;
            }
            QMessageBox QPushButton[text="취소"] {
                background-color: #9E9E9E;
                color: white;
                border: 2px solid #757575;
            }
            QMessageBox QPushButton[text="취소"]:hover {
                background-color: #757575;
            }
        """)

    def _create_styled_button(self, text, color_type):
        """스타일이 적용된 버튼을 생성하는 헬퍼 메서드"""
        btn = QPushButton(text)
        
        if color_type == 'primary':  # 파란색
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 6px;
                    font-weight: bold;
                    min-width: 90px;
                    min-height: 40px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
                QPushButton:pressed {
                    background-color: #0D47A1;
                }
            """)
        elif color_type == 'danger':  # 빨간색
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #F44336;
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 6px;
                    font-weight: bold;
                    min-width: 90px;
                    min-height: 40px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #D32F2F;
                }
                QPushButton:pressed {
                    background-color: #B71C1C;
                }
            """)
        elif color_type == 'secondary':  # 회색
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #9E9E9E;
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 6px;
                    font-weight: bold;
                    min-width: 90px;
                    min-height: 40px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #757575;
                }
                QPushButton:pressed {
                    background-color: #424242;
                }
            """)
        
        return btn

    def show_yes_no_question(self, title, message):
        """Yes/No 순서로 버튼을 표시하는 커스텀 다이얼로그"""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.resize(500, 250)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 메시지 텍스트
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        message_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                line-height: 1.5;
                color: inherit;
                background: transparent;
                padding: 10px;
            }
        """)
        layout.addWidget(message_label)
        layout.addStretch()
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.addStretch()
        
        yes_btn = self._create_styled_button("예", 'primary')
        no_btn = self._create_styled_button("아니오", 'danger')
        
        button_layout.addWidget(yes_btn)
        button_layout.addWidget(no_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 결과 변수
        result = False
        
        def on_yes():
            nonlocal result
            result = True
            dialog.accept()
        
        def on_no():
            dialog.reject()
        
        yes_btn.clicked.connect(on_yes)
        no_btn.clicked.connect(on_no)
        yes_btn.setDefault(True)
        yes_btn.setFocus()
        
        # 테마 적용
        self._apply_dialog_theme(dialog)
        
        dialog.exec()
        return result

    def _apply_dialog_theme(self, dialog):
        """다이얼로그에 테마를 적용하는 헬퍼 메서드"""
        if self.is_dark_mode():
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
            """)
        else:
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #ffffff;
                    color: #000000;
                }
            """)

    def show_yes_no_cancel_question(self, title, message):
        """Yes/No/Cancel 순서로 버튼을 표시하는 커스텀 다이얼로그"""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.resize(550, 400)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 스크롤 가능한 메시지 텍스트 영역
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        message_widget = QWidget()
        message_layout = QVBoxLayout(message_widget)
        message_layout.setContentsMargins(10, 10, 10, 10)
        
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        message_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                line-height: 1.5;
                color: inherit;
                background: transparent;
            }
        """)
        message_layout.addWidget(message_label)
        message_layout.addStretch()
        
        scroll_area.setWidget(message_widget)
        layout.addWidget(scroll_area)
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.addStretch()
        
        yes_btn = self._create_styled_button("예", 'primary')
        no_btn = self._create_styled_button("아니오", 'danger')
        cancel_btn = self._create_styled_button("취소", 'secondary')
        
        button_layout.addWidget(yes_btn)
        button_layout.addWidget(no_btn)
        button_layout.addWidget(cancel_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 결과 변수
        result = None
        
        def on_yes():
            nonlocal result
            result = "yes"
            dialog.accept()
            
        def on_no():
            nonlocal result
            result = "no"
            dialog.accept()
            
        def on_cancel():
            nonlocal result
            result = "cancel"
            dialog.reject()
        
        yes_btn.clicked.connect(on_yes)
        no_btn.clicked.connect(on_no)
        cancel_btn.clicked.connect(on_cancel)
        yes_btn.setDefault(True)
        
        # 스크롤 영역을 포함한 테마 적용
        self._apply_dialog_with_scroll_theme(dialog)
        
        dialog.exec()
        return result if result is not None else "cancel"

    def _apply_dialog_with_scroll_theme(self, dialog):
        """스크롤 영역이 있는 다이얼로그에 테마를 적용하는 헬퍼 메서드"""
        if self.is_dark_mode():
            dialog.setStyleSheet("""
                QDialog { 
                    background-color: #2b2b2b; 
                    color: #ffffff; 
                }
                QScrollArea {
                    background-color: transparent;
                    border: 1px solid #555555;
                    border-radius: 4px;
                }
                QScrollBar:vertical {
                    background-color: #404040;
                    width: 12px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical {
                    background-color: #666666;
                    border-radius: 6px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #777777;
                }
            """)
        else:
            dialog.setStyleSheet("""
                QDialog { 
                    background-color: #ffffff; 
                    color: #000000; 
                }
                QScrollArea {
                    background-color: transparent;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                }
                QScrollBar:vertical {
                    background-color: #f0f0f0;
                    width: 12px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical {
                    background-color: #cccccc;
                    border-radius: 6px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #aaaaaa;
                }
            """)

    def check_theme_change(self):

        current_is_dark = self.is_dark_mode()
        if self.last_dark_mode != current_is_dark:
            self.last_dark_mode = current_is_dark
            self.apply_styles()
            self.setup_message_box_styles()

    def closeEvent(self, event):
        """메인 윈도우 종료 시 모든 프로그램 완전 종료"""
        try:
            # 실행 중인 모든 스레드 종료
            if hasattr(self, 'current_worker') and self.current_worker:
                if self.current_worker.isRunning():
                    self.current_worker.terminate()
                    self.current_worker.wait(1000)
            
            if hasattr(self, 'compressed_upload_thread') and self.compressed_upload_thread:
                if self.compressed_upload_thread.isRunning():
                    self.compressed_upload_thread.terminate()
                    self.compressed_upload_thread.wait(1000)
            
            if hasattr(self, 'multi_upload_thread') and self.multi_upload_thread:
                if self.multi_upload_thread.isRunning():
                    self.multi_upload_thread.terminate()
                    self.multi_upload_thread.wait(1000)
            
            if hasattr(self, 'folder_upload_thread') and self.folder_upload_thread:
                if self.folder_upload_thread.isRunning():
                    self.folder_upload_thread.terminate()
                    self.folder_upload_thread.wait(1000)
            
            if hasattr(self, 'upload_thread') and self.upload_thread:
                if self.upload_thread.isRunning():
                    self.upload_thread.terminate()
                    self.upload_thread.wait(1000)
            
            # 콘솔 출력 복원
            if hasattr(self, 'console_output'):
                self.console_output.restore()
            
            # 애플리케이션 완전 종료
            QApplication.quit()
            
        except Exception as e:
            print(f"종료 처리 중 오류: {str(e)}")
        finally:
            event.accept()

    def convert_storage_class(self):

        if self.current_storage_type != 'ncloud':
            return

        # Storage Class 변경 기능 안내 메시지
        QMessageBox.information(
            self, 
            "Storage Class 변경 기능 안내",
            "Storage Class 변경 기능은 NCloud에서 아직 출시 안됨.\n\n"
            "• 예상 출시: 2025년 하반기\n"
            "• 지원 예정: STANDARD ↔ DEEP_ARCHIVE 변경\n"
            "• 기능 출시 시 업데이트하겠습니다.\n\n"
            "현재는 업로드 시 Storage Class를 선택하여 사용해주세요."
        )

    def get_storage_class_for_upload(self):
        """업로드 시 Storage Class 선택"""
        if self.current_storage_type != 'ncloud':
            return 'STANDARD'
            
        items = ["STANDARD (일반)", "DEEP_ARCHIVE (아카이브)"]
        item, ok = QInputDialog.getItem(
            self, "Storage Class 선택",
            "업로드할 파일의 Storage Class를 선택하세요:",
            items, 0, False
        )
        
        if not ok:
            return None  # 사용자가 취소한 경우
            
        return "STANDARD" if "STANDARD" in item else "DEEP_ARCHIVE"

def main():
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("네이버 클라우드 통합 Storage GUI Client")
        app.setApplicationVersion("2.0.0")
        app.setOrganizationName("Naver Cloud Platform")

        app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeMenuBar, False)
        app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, False)

        window = IntegratedStorageGUI()
        window.show()

        sys.exit(app.exec())

    except Exception as e:
        print(f"애플리케이션 실행 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()