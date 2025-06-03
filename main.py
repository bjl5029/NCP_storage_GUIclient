import sys
import os
import json
import zipfile
import tempfile
import shutil
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                           QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, 
                           QFileDialog, QProgressBar, QComboBox, QListWidget, 
                           QSplitter, QGroupBox, QGridLayout, QMessageBox,
                           QInputDialog, QListWidgetItem, QTabWidget, QCheckBox,
                           QTreeWidget, QTreeWidgetItem, QToolButton, QSizePolicy)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor
from storage_client import NaverArchiveStorageClient


class UploadThread(QThread):
    """파일 업로드 스레드"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, client, container_name, object_name, file_path):
        super().__init__()
        self.client = client
        self.container_name = container_name
        self.object_name = object_name
        self.file_path = file_path
        
    def run(self):
        try:
            success = self.client.upload_file(
                self.container_name, 
                self.object_name, 
                self.file_path,
                self.progress.emit
            )
            self.finished.emit(success, "업로드가 완료되었습니다." if success else "업로드에 실패했습니다.")
        except Exception as e:
            self.finished.emit(False, f"업로드 오류: {str(e)}")


class DownloadThread(QThread):
    """파일 다운로드 스레드"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, client, container_name, object_name, save_path):
        super().__init__()
        self.client = client
        self.container_name = container_name
        self.object_name = object_name
        self.save_path = save_path
        
    def run(self):
        try:
            success = self.client.download_file(
                self.container_name, 
                self.object_name, 
                self.save_path,
                self.progress.emit
            )
            self.finished.emit(success, "다운로드가 완료되었습니다." if success else "다운로드에 실패했습니다.")
        except Exception as e:
            self.finished.emit(False, f"다운로드 오류: {str(e)}")


class FolderUploadThread(QThread):
    """폴더 업로드 스레드 (개선된 에러 핸들링)"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, client, container_name, local_folder_path, remote_base_path):
        super().__init__()
        self.client = client
        self.container_name = container_name
        self.local_folder_path = local_folder_path
        self.remote_base_path = remote_base_path
        
    def run(self):
        try:
            print(f"폴더 업로드 스레드 시작")
            print(f"로컬 폴더: {self.local_folder_path}")
            print(f"원격 경로: {self.remote_base_path}")
            print(f"버킷: {self.container_name}")
            
            success = self.client.upload_folder(
                self.container_name, 
                self.local_folder_path,
                self.remote_base_path,
                self.progress.emit
            )
            
            if success:
                message = "폴더 업로드가 완료되었습니다."
                print(f"폴더 업로드 성공: {message}")
            else:
                message = "일부 파일의 업로드에 실패했습니다. 콘솔 로그를 확인해주세요."
                print(f"폴더 업로드 부분 실패: {message}")
            
            self.finished.emit(success, message)
            
        except Exception as e:
            error_msg = f"폴더 업로드 오류: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self.finished.emit(False, error_msg)


class CompressedUploadThread(QThread):
    """압축 파일 업로드 스레드"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    status = pyqtSignal(str)
    
    def __init__(self, client, container_name, file_paths, folders, current_path, zip_filename):
        super().__init__()
        self.client = client
        self.container_name = container_name
        self.file_paths = file_paths if file_paths else []
        self.folders = folders if folders else []
        self.current_path = current_path
        self.zip_filename = zip_filename
        self.temp_zip_path = None
        
    def run(self):
        try:
            print(f"압축 업로드 시작")
            print(f"파일 수: {len(self.file_paths)}, 폴더 수: {len(self.folders)}")
            
            self.status.emit("압축 파일 생성 중...")
            self.progress.emit(5)
            
            temp_dir = tempfile.mkdtemp()
            self.temp_zip_path = os.path.join(temp_dir, self.zip_filename)
            
            with zipfile.ZipFile(self.temp_zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
                for i, file_path in enumerate(self.file_paths):
                    if os.path.exists(file_path):
                        arc_name = os.path.basename(file_path)
                        zipf.write(file_path, arc_name)
                        print(f"파일 압축 추가: {arc_name}")
                
                for folder_path in self.folders:
                    if os.path.exists(folder_path):
                        folder_name = os.path.basename(folder_path)
                        for root, dirs, files in os.walk(folder_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                relative_path = os.path.relpath(file_path, folder_path)
                                arc_name = os.path.join(folder_name, relative_path)
                                zipf.write(file_path, arc_name)
                                print(f"폴더 파일 압축 추가: {arc_name}")
            
            zip_size = os.path.getsize(self.temp_zip_path)
            print(f"압축 파일 생성 완료: {self.client.format_file_size(zip_size)}")
            
            self.status.emit(f"압축 파일 업로드 중... ({self.client.format_file_size(zip_size)})")
            self.progress.emit(10)
            
            if self.current_path:
                remote_path = f"{self.current_path}{self.zip_filename}"
            else:
                remote_path = self.zip_filename
            
            def upload_progress_callback(progress):
                final_progress = 10 + int(progress * 0.9)
                self.progress.emit(final_progress)
                self.status.emit(f"압축 파일 업로드 중... {progress}%")
            
            success = self.client.upload_file(
                self.container_name, 
                remote_path, 
                self.temp_zip_path, 
                upload_progress_callback
            )
            
            if success:
                self.progress.emit(100)
                self.status.emit("압축 업로드 완료!")
                
                file_count = len(self.file_paths)
                folder_count = len(self.folders)
                total_items = file_count + folder_count
                
                message = f"압축 파일 업로드가 완료되었습니다!\n"
                message += f"파일명: {self.zip_filename}\n"
                message += f"압축된 항목: {file_count}개 파일, {folder_count}개 폴더 (총 {total_items}개)\n"
                message += f"압축 후 크기: {self.client.format_file_size(zip_size)}"
                
                self.finished.emit(True, message)
            else:
                self.finished.emit(False, "압축 파일 업로드에 실패했습니다.")
                
        except Exception as e:
            error_msg = f"압축 업로드 오류: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self.finished.emit(False, error_msg)
        
        finally:
            if self.temp_zip_path and os.path.exists(self.temp_zip_path):
                try:
                    shutil.rmtree(os.path.dirname(self.temp_zip_path))
                    print("임시 압축 파일 정리 완료")
                except Exception as e:
                    print(f"임시 파일 정리 오류: {e}")


class MultiFileUploadThread(QThread):
    """여러 파일 업로드 스레드"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, client, container_name, file_paths, current_path):
        super().__init__()
        self.client = client
        self.container_name = container_name
        self.file_paths = file_paths
        self.current_path = current_path
        
    def run(self):
        try:
            print(f"여러 파일 업로드 시작: {len(self.file_paths)}개 파일")
            
            total_files = len(self.file_paths)
            uploaded_files = 0
            failed_files = []
            
            for i, file_path in enumerate(self.file_paths):
                try:
                    file_name = os.path.basename(file_path)
                    
                    if self.current_path:
                        remote_path = f"{self.current_path}{file_name}"
                    else:
                        remote_path = file_name
                    
                    print(f"업로드 중 ({i+1}/{total_files}): {file_name}")
                    
                    def file_progress_callback(file_progress):
                        current_file_contribution = file_progress / total_files
                        completed_files_contribution = (uploaded_files / total_files) * 100
                        total_progress = int(completed_files_contribution + current_file_contribution)
                        self.progress.emit(min(total_progress, 100))
                    
                    success = self.client.upload_file(
                        self.container_name, 
                        remote_path, 
                        file_path, 
                        file_progress_callback
                    )
                    
                    if success:
                        uploaded_files += 1
                        print(f"업로드 성공: {file_name}")
                    else:
                        failed_files.append(file_name)
                        print(f"업로드 실패: {file_name}")
                
                except Exception as e:
                    print(f"파일 처리 오류 ({file_name}): {str(e)}")
                    failed_files.append(file_name)
            
            if failed_files:
                message = f"{uploaded_files}/{total_files}개 파일 업로드 완료.\n실패한 파일:\n" + "\n".join(failed_files)
                self.finished.emit(len(failed_files) == 0, message)
            else:
                message = f"{total_files}개 파일 업로드가 모두 완료되었습니다."
                self.finished.emit(True, message)
                
        except Exception as e:
            error_msg = f"여러 파일 업로드 오류: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self.finished.emit(False, error_msg)


class FolderDownloadThread(QThread):
    """폴더 다운로드 스레드"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, client, container_name, folder_path, local_base_path):
        super().__init__()
        self.client = client
        self.container_name = container_name
        self.folder_path = folder_path
        self.local_base_path = local_base_path
        
    def run(self):
        try:
            success = self.client.download_folder(
                self.container_name, 
                self.folder_path,
                self.local_base_path,
                self.progress.emit
            )
            self.finished.emit(success, "폴더 다운로드가 완료되었습니다." if success else "폴더 다운로드에 실패했습니다.")
        except Exception as e:
            self.finished.emit(False, f"폴더 다운로드 오류: {str(e)}")


class MultiFileDownloadThread(QThread):
    """여러 파일 다운로드 스레드"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, client, container_name, items, base_download_path):
        super().__init__()
        self.client = client
        self.container_name = container_name
        self.items = items
        self.base_download_path = base_download_path
        
    def run(self):
        try:
            total_items = len(self.items)
            completed_items = 0
            
            for item in self.items:
                if item['type'] == 'file':
                    local_path = os.path.join(self.base_download_path, item['name'])
                    success = self.client.download_file(
                        self.container_name,
                        item['full_path'],
                        local_path
                    )
                elif item['type'] == 'folder':
                    folder_local_path = os.path.join(self.base_download_path, item['name'])
                    os.makedirs(folder_local_path, exist_ok=True)
                    success = self.client.download_folder(
                        self.container_name,
                        item['full_path'],
                        folder_local_path
                    )
                
                if not success:
                    self.finished.emit(False, f"'{item['name']}' 다운로드에 실패했습니다.")
                    return
                
                completed_items += 1
                progress = int((completed_items / total_items) * 100)
                self.progress.emit(progress)
            
            self.finished.emit(True, f"{total_items}개 항목의 다운로드가 완료되었습니다.")
            
        except Exception as e:
            self.finished.emit(False, f"다중 다운로드 오류: {str(e)}")


class NaverArchiveStorageGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.client = NaverArchiveStorageClient()
        self.current_container = None
        self.current_path = ""
        self.config_file = "config.json"
        
        self.init_ui()
        self.load_config()
        
        self.apply_styles()
        
        self.theme_timer = QTimer()
        self.theme_timer.timeout.connect(self.check_theme_change)
        self.theme_timer.start(1000)
        self.last_dark_mode = self.is_dark_mode()
    
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("네이버 클라우드 Archive Storage 관리자")
        self.setGeometry(100, 100, 1400, 900)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QVBoxLayout(main_widget)
        
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        settings_tab = QWidget()
        tab_widget.addTab(settings_tab, "설정")
        self.init_settings_tab(settings_tab)
        
        files_tab = QWidget()
        tab_widget.addTab(files_tab, "파일 관리")
        self.init_files_tab(files_tab)
        
        self.statusBar().showMessage("설정 정보를 입력하고 연결하세요.")
        
    def init_settings_tab(self, tab):
        """설정 탭 초기화"""
        layout = QVBoxLayout(tab)
        
        auth_group = QGroupBox("인증 정보")
        auth_layout = QGridLayout(auth_group)
        
        auth_layout.addWidget(QLabel("Access Key ID:"), 0, 0)
        self.access_key_edit = QLineEdit()
        auth_layout.addWidget(self.access_key_edit, 0, 1)
        
        auth_layout.addWidget(QLabel("Secret Key:"), 1, 0)
        self.secret_key_edit = QLineEdit()
        self.secret_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        auth_layout.addWidget(self.secret_key_edit, 1, 1)
        
        auth_layout.addWidget(QLabel("Domain ID:"), 2, 0)
        self.domain_id_edit = QLineEdit()
        auth_layout.addWidget(self.domain_id_edit, 2, 1)
        
        auth_layout.addWidget(QLabel("Project ID:"), 3, 0)
        self.project_id_edit = QLineEdit()
        auth_layout.addWidget(self.project_id_edit, 3, 1)
        
        layout.addWidget(auth_group)
        
        button_layout = QHBoxLayout()
        
        self.save_config_btn = QPushButton("인증 저장")
        self.save_config_btn.clicked.connect(self.save_config)
        button_layout.addWidget(self.save_config_btn)
        
        self.test_connection_btn = QPushButton("연결")
        self.test_connection_btn.clicked.connect(self.test_connection)
        button_layout.addWidget(self.test_connection_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setMaximumHeight(200)
        
        if self.is_dark_mode():
            help_content = """
            <div style="color: #ffffff; font-family: Arial, sans-serif;">
            <h3 style="color: #0078d4;"> 사용가이드</h3>
            <ol style="color: #ffffff;">
            <li><b style="color: #ffffff;">네이버 클라우드 플랫폼</b> 로그인</li>
            <li><b style="color: #ffffff;">마이페이지 → 계정 관리 → 인증키 관리</b>에서 API 인증키 생성 또는 확인</li>
            <li><b style="color: #ffffff;">Archive Storage 콘솔</b>에서 <b style="color: #ffffff;">[API 이용 정보 확인]</b> 버튼을 클릭하여 Domain ID와 Project ID를 확인</li>
            <li>위 정보들을 입력하고 <b style="color: #ffffff;">연결</b> 클릭</li>
            </ol>
            </div>
            """
        else:
            help_content = """
            <div style="color: #000000; font-family: Arial, sans-serif;">
            <h3 style="color: #0078d4;">설정 방법</h3>
            <ol style="color: #000000;">
            <li><b style="color: #000000;">네이버 클라우드 플랫폼</b>에 로그인하세요</li>
            <li><b style="color: #000000;">마이페이지 → 계정 관리 → 인증키 관리</b>에서 API 인증키를 생성하세요</li>
            <li><b style="color: #000000;">Archive Storage 콘솔</b>에서 이용 신청 후 <b style="color: #000000;">[API 이용 정보 확인]</b> 버튼을 클릭하여 Domain ID와 Project ID를 확인하세요</li>
            <li>위 정보들을 입력하고 <b style="color: #000000;">연결 테스트</b>를 클릭하세요</li>
            </ol>
            </div>
            """
        
        help_text.setHtml(help_content)
        layout.addWidget(help_text)
        
        layout.addStretch()
        
    def init_files_tab(self, tab):
        """파일 관리 탭 초기화 (개선된 UI 레이아웃)"""
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        
        container_group = QGroupBox("버킷 관리")
        container_layout = QGridLayout(container_group)
        container_layout.setSpacing(8)
        
        container_layout.addWidget(QLabel("버킷:"), 0, 0)
        self.container_combo = QComboBox()
        self.container_combo.currentTextChanged.connect(self.on_container_changed)
        self.container_combo.setMinimumWidth(200)
        container_layout.addWidget(self.container_combo, 0, 1, 1, 2)
        
        self.refresh_containers_btn = QPushButton("새로고침")
        self.refresh_containers_btn.clicked.connect(self.refresh_containers)
        self.refresh_containers_btn.setFixedWidth(100)
        container_layout.addWidget(self.refresh_containers_btn, 0, 3)
        
        self.create_container_btn = QPushButton("버킷 생성")
        self.create_container_btn.clicked.connect(self.create_container)
        self.create_container_btn.setFixedWidth(120)
        container_layout.addWidget(self.create_container_btn, 0, 4)
        
        container_layout.setColumnStretch(2, 1)
        layout.addWidget(container_group)
        
        navigation_group = QGroupBox("폴더 탐색")
        navigation_layout = QHBoxLayout(navigation_group)
        navigation_layout.setSpacing(8)
        
        self.back_btn = QToolButton()
        self.back_btn.setText("← 뒤로")
        self.back_btn.clicked.connect(self.go_back)
        self.back_btn.setEnabled(False)
        self.back_btn.setMinimumWidth(80)
        navigation_layout.addWidget(self.back_btn)
        
        self.path_label = QLabel("경로: /")
        self.path_label.setStyleSheet("font-weight: bold; padding: 5px;")
        navigation_layout.addWidget(self.path_label)
        
        navigation_layout.addStretch()
        
        self.create_folder_btn = QPushButton("새 폴더")
        self.create_folder_btn.clicked.connect(self.create_folder)
        self.create_folder_btn.setFixedWidth(100)
        navigation_layout.addWidget(self.create_folder_btn)
        
        layout.addWidget(navigation_group)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        file_area_widget = QWidget()
        file_area_layout = QVBoxLayout(file_area_widget)
        file_area_layout.setSpacing(8)
        
        file_header_group = QGroupBox("파일 및 폴더 목록")
        file_header_layout = QHBoxLayout(file_header_group)
        
        self.select_all_checkbox = QCheckBox("전체 선택")
        self.select_all_checkbox.stateChanged.connect(self.toggle_select_all)
        file_header_layout.addWidget(self.select_all_checkbox)
        
        file_header_layout.addStretch()
        
        file_area_layout.addWidget(file_header_group)
        
        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        file_area_layout.addWidget(self.file_list)
        
        file_buttons_group = QGroupBox("파일 작업")
        file_buttons_layout = QHBoxLayout(file_buttons_group)
        file_buttons_layout.setSpacing(8)
        
        self.refresh_files_btn = QPushButton("새로고침")
        self.refresh_files_btn.clicked.connect(self.refresh_files)
        self.refresh_files_btn.setFixedWidth(100)
        file_buttons_layout.addWidget(self.refresh_files_btn)
        
        self.delete_selected_btn = QPushButton("선택 항목 삭제")
        self.delete_selected_btn.clicked.connect(self.delete_selected_items)
        self.delete_selected_btn.setFixedWidth(120)
        file_buttons_layout.addWidget(self.delete_selected_btn)
        
        file_buttons_layout.addStretch()
        
        file_area_layout.addWidget(file_buttons_group)
        splitter.addWidget(file_area_widget)
        
        operation_widget = QWidget()
        operation_layout = QVBoxLayout(operation_widget)
        operation_layout.setSpacing(10)
        
        upload_group = QGroupBox("업로드")
        upload_layout = QVBoxLayout(upload_group)
        upload_layout.setSpacing(8)
        
        self.upload_path_label = QLabel("업로드 위치: /")
        self.upload_path_label.setStyleSheet("font-weight: bold; color: #0078d4; padding: 5px; background-color: rgba(0, 120, 212, 0.1); border-radius: 4px;")
        upload_layout.addWidget(self.upload_path_label)
        
        file_upload_group = QGroupBox("파일 업로드")
        file_upload_inner_layout = QVBoxLayout(file_upload_group)
        file_upload_inner_layout.setSpacing(5)
        
        self.selected_file_label = QLabel("선택된 파일: 없음")
        self.selected_file_label.setWordWrap(True)
        self.selected_file_label.setStyleSheet("padding: 5px; background-color: rgba(255, 255, 255, 0.05); border-radius: 3px;")
        file_upload_inner_layout.addWidget(self.selected_file_label)
        
        file_btn_layout = QGridLayout()
        file_btn_layout.setSpacing(5)
        
        self.select_file_btn = QPushButton("파일 선택 (여러 개 가능)")
        self.select_file_btn.clicked.connect(self.select_file_for_upload)
        file_btn_layout.addWidget(self.select_file_btn, 0, 0, 1, 2)
        
        self.upload_file_btn = QPushButton("파일 업로드")
        self.upload_file_btn.clicked.connect(self.upload_file)
        self.upload_file_btn.setEnabled(False)
        file_btn_layout.addWidget(self.upload_file_btn, 1, 0, 1, 2)
        
        compression_info = QLabel("여러 파일 선택 시 압축 후 업로드 옵션 여부를 묻습니다.")
        compression_info.setWordWrap(True)
        compression_info.setStyleSheet("color: #0078d4; font-size: 10px; padding: 3px; font-style: italic;")
        file_btn_layout.addWidget(compression_info, 2, 0, 1, 2)
        
        file_upload_inner_layout.addLayout(file_btn_layout)
        upload_layout.addWidget(file_upload_group)
        
        folder_upload_group = QGroupBox("폴더 업로드")
        folder_upload_inner_layout = QVBoxLayout(folder_upload_group)
        folder_upload_inner_layout.setSpacing(5)
        
        self.selected_folder_label = QLabel("선택된 폴더: 없음")
        self.selected_folder_label.setWordWrap(True)
        self.selected_folder_label.setStyleSheet("padding: 5px; background-color: rgba(255, 255, 255, 0.05); border-radius: 3px;")
        folder_upload_inner_layout.addWidget(self.selected_folder_label)
        
        folder_btn_layout = QGridLayout()
        folder_btn_layout.setSpacing(5)
        
        self.select_folder_btn = QPushButton("폴더 선택")
        self.select_folder_btn.clicked.connect(self.select_folder_for_upload)
        folder_btn_layout.addWidget(self.select_folder_btn, 0, 0, 1, 2)
        
        self.upload_folder_btn = QPushButton("폴더 업로드")
        self.upload_folder_btn.clicked.connect(self.upload_folder)
        self.upload_folder_btn.setEnabled(False)
        folder_btn_layout.addWidget(self.upload_folder_btn, 1, 0, 1, 2)
        
        folder_compression_info = QLabel("폴더 선택시 압축 후 업로드 여부를 묻습니다.")
        folder_compression_info.setWordWrap(True)
        folder_compression_info.setStyleSheet("color: #0078d4; font-size: 10px; padding: 3px; font-style: italic;")
        folder_btn_layout.addWidget(folder_compression_info, 2, 0, 1, 2)
        
        folder_upload_inner_layout.addLayout(folder_btn_layout)
        upload_layout.addWidget(folder_upload_group)
        
        operation_layout.addWidget(upload_group)
        
        download_group = QGroupBox("다운로드")
        download_layout = QVBoxLayout(download_group)
        download_layout.setSpacing(8)
        
        self.selected_items_label = QLabel("선택된 항목: 없음")
        self.selected_items_label.setStyleSheet("font-weight: bold; color: #0078d4; padding: 5px; background-color: rgba(0, 120, 212, 0.1); border-radius: 4px;")
        self.selected_items_label.setWordWrap(True)
        download_layout.addWidget(self.selected_items_label)
        
        download_info = QLabel("체크박스로 항목을 선택하고 다운로드 버튼을 클릭하세요.\n폴더를 더블클릭하면 해당 폴더로 이동합니다.")
        download_info.setWordWrap(True)
        download_info.setStyleSheet("color: #888888; font-size: 11px; padding: 5px;")
        download_layout.addWidget(download_info)
        
        self.download_selected_btn = QPushButton("선택한 항목 다운로드")
        self.download_selected_btn.clicked.connect(self.download_selected_items)
        download_layout.addWidget(self.download_selected_btn)
        
        operation_layout.addWidget(download_group)
        
        progress_group = QGroupBox("작업 진행률")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(5)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("대기 중")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setStyleSheet("font-weight: bold; padding: 3px;")
        progress_layout.addWidget(self.progress_label)
        
        operation_layout.addWidget(progress_group)
        
        operation_layout.addStretch()
        splitter.addWidget(operation_widget)
        
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([800, 400])
        
        layout.addWidget(splitter)
        
    def apply_styles(self):
        """시스템 테마에 맞는 스타일 적용"""
        palette = self.palette()
        
        is_dark_mode = self.is_dark_mode()
        
        if is_dark_mode:
            self.apply_dark_theme()
        else:
            self.apply_light_theme()
    
    def is_dark_mode(self):
        """다크모드 여부 확인"""
        palette = self.palette()
        bg_color = palette.color(QPalette.ColorRole.Window)
        brightness = (bg_color.red() + bg_color.green() + bg_color.blue()) / 3
        return brightness < 128
    
    def apply_dark_theme(self):
        """다크 테마 스타일 적용"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            
            QTabWidget::pane {
                border: 1px solid #555555;
                background-color: #2b2b2b;
            }
            
            QTabWidget::tab-bar {
                alignment: left;
            }
            
            QTabBar::tab {
                background-color: #3c3c3c;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            
            QTabBar::tab:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
            
            QTabBar::tab:hover {
                background-color: #4c4c4c;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555555;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
                color: #ffffff;
                background-color: #2b2b2b;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #ffffff;
            }
            
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            
            QPushButton:hover {
                background-color: #106ebe;
            }
            
            QPushButton:pressed {
                background-color: #005a9e;
            }
            
            QPushButton:disabled {
                background-color: #484848;
                color: #999999;
            }
            
            QToolButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            
            QToolButton:hover {
                background-color: #106ebe;
            }
            
            QToolButton:disabled {
                background-color: #484848;
                color: #999999;
            }
            
            QLineEdit {
                padding: 8px;
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: #3c3c3c;
                color: #ffffff;
                selection-background-color: #0078d4;
            }
            
            QLineEdit:focus {
                border: 2px solid #0078d4;
            }
            
            QComboBox {
                padding: 8px;
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: #3c3c3c;
                color: #ffffff;
                selection-background-color: #0078d4;
            }
            
            QComboBox::drop-down {
                border: none;
                background-color: #0078d4;
                width: 20px;
                border-radius: 0px 4px 4px 0px;
            }
            
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #ffffff;
                margin: 0px 4px;
            }
            
            QComboBox QAbstractItemView {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                selection-background-color: #0078d4;
            }
            
            QListWidget {
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: #3c3c3c;
                color: #ffffff;
                alternate-background-color: #404040;
                outline: none;
            }
            
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #484848;
                min-height: 32px;
            }
            
            QListWidget::item:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
            
            QListWidget::item:hover {
                background-color: #4c4c4c;
            }
            
            QTextEdit {
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: #3c3c3c;
                color: #ffffff;
                selection-background-color: #0078d4;
            }
            
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 4px;
                text-align: center;
                background-color: #3c3c3c;
                color: #ffffff;
            }
            
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
            }
            
            QLabel {
                color: #ffffff;
            }
            
            QCheckBox {
                color: #ffffff;
                spacing: 5px;
            }
            
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #555555;
                border-radius: 2px;
                background-color: #3c3c3c;
            }
            
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border: 1px solid #0078d4;
            }
            
            QCheckBox::indicator:checked::after {
                content: "✓";
                color: #ffffff;
                font-weight: bold;
            }
            
            QStatusBar {
                background-color: #2b2b2b;
                color: #ffffff;
                border-top: 1px solid #555555;
            }
            
            QSplitter::handle {
                background-color: #555555;
            }
            
            QSplitter::handle:horizontal {
                width: 2px;
            }
            
            QSplitter::handle:vertical {
                height: 2px;
            }
        """)
    
    def apply_light_theme(self):
        """라이트 테마 스타일 적용"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ffffff;
                color: #000000;
            }
            
            QTabWidget::pane {
                border: 1px solid #cccccc;
                background-color: #ffffff;
            }
            
            QTabWidget::tab-bar {
                alignment: left;
            }
            
            QTabBar::tab {
                background-color: #f0f0f0;
                color: #000000;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                border: 1px solid #cccccc;
                border-bottom: none;
            }
            
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #000000;
                border-bottom: 1px solid #ffffff;
            }
            
            QTabBar::tab:hover {
                background-color: #e6e6e6;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
                color: #000000;
                background-color: #ffffff;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #000000;
            }
            
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            
            QPushButton:hover {
                background-color: #106ebe;
            }
            
            QPushButton:pressed {
                background-color: #005a9e;
            }
            
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            
            QToolButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            
            QToolButton:hover {
                background-color: #106ebe;
            }
            
            QToolButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            
            QLineEdit {
                padding: 8px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #0078d4;
            }
            
            QLineEdit:focus {
                border: 2px solid #0078d4;
            }
            
            QComboBox {
                padding: 8px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #0078d4;
            }
            
            QComboBox::drop-down {
                border: none;
                background-color: #0078d4;
                width: 20px;
                border-radius: 0px 4px 4px 0px;
            }
            
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #ffffff;
                margin: 0px 4px;
            }
            
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #cccccc;
                selection-background-color: #0078d4;
                selection-color: #ffffff;
            }
            
            QListWidget {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #ffffff;
                color: #000000;
                alternate-background-color: #f5f5f5;
                outline: none;
            }
            
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eeeeee;
                min-height: 32px;
            }
            
            QListWidget::item:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
            
            QListWidget::item:hover {
                background-color: #e6f3ff;
            }
            
            QTextEdit {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #0078d4;
            }
            
            QProgressBar {
                border: 1px solid #cccccc;
                border-radius: 4px;
                text-align: center;
                background-color: #ffffff;
                color: #000000;
            }
            
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
            }
            
            QLabel {
                color: #000000;
            }
            
            QCheckBox {
                color: #000000;
                spacing: 5px;
            }
            
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #cccccc;
                border-radius: 2px;
                background-color: #ffffff;
            }
            
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border: 1px solid #0078d4;
            }
            
            QCheckBox::indicator:hover {
                border: 1px solid #0078d4;
            }
            
            QStatusBar {
                background-color: #f0f0f0;
                color: #000000;
                border-top: 1px solid #cccccc;
            }
            
            QSplitter::handle {
                background-color: #cccccc;
            }
            
            QSplitter::handle:horizontal {
                width: 2px;
            }
            
            QSplitter::handle:vertical {
                height: 2px;
            }
        """)
    
    def load_config(self):
        """설정 파일 로드"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.access_key_edit.setText(config.get('access_key', ''))
                    self.secret_key_edit.setText(config.get('secret_key', ''))
                    self.domain_id_edit.setText(config.get('domain_id', ''))
                    self.project_id_edit.setText(config.get('project_id', ''))
        except Exception as e:
            print(f"설정 로드 오류: {str(e)}")
    
    def save_config(self):
        """설정 파일 저장"""
        try:
            config = {
                'access_key': self.access_key_edit.text(),
                'secret_key': self.secret_key_edit.text(),
                'domain_id': self.domain_id_edit.text(),
                'project_id': self.project_id_edit.text()
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            
            QMessageBox.information(self, "저장 완료", "설정이 저장되었습니다.")
            
        except Exception as e:
            QMessageBox.critical(self, "저장 오류", f"설정 저장 중 오류가 발생했습니다: {str(e)}")
    
    def test_connection(self):
        """연결 테스트"""
        try:
            self.client.set_credentials(
                self.access_key_edit.text(),
                self.secret_key_edit.text(),
                self.domain_id_edit.text(),
                self.project_id_edit.text()
            )
            
            if self.client.get_token():
                QMessageBox.information(self, "연결 성공", "네이버 클라우드 Archive Storage에 성공적으로 연결되었습니다!")
                self.statusBar().showMessage("연결됨 - 파일 관리 탭에서 작업하세요.")
                self.refresh_containers()
            else:
                QMessageBox.critical(self, "연결 실패", "연결에 실패했습니다. 인증 정보를 다시 확인해주세요.")
                
        except Exception as e:
            QMessageBox.critical(self, "연결 오류", f"연결 중 오류가 발생했습니다: {str(e)}")
    
    def refresh_containers(self):
        try:
            containers = self.client.get_containers()
            self.container_combo.clear()
            
            for container in containers:
                self.container_combo.addItem(container['name'])
            
            if containers:
                self.current_container = self.container_combo.currentText()
                self.current_path = ""
                self.update_path_display()
                self.refresh_files()
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"버킷 목록을 가져오는 중 오류가 발생했습니다: {str(e)}")
    
    def create_container(self):
        """새 버킷 생성"""
        name, ok = QInputDialog.getText(self, "버킷 생성", "버킷 이름을 입력하세요:")
        
        if ok and name:
            try:
                if self.client.create_container(name):
                    QMessageBox.information(self, "성공", f"버킷 '{name}'이 생성되었습니다.")
                    self.refresh_containers()
                else:
                    QMessageBox.critical(self, "실패", "버킷 생성에 실패했습니다.")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"버킷 생성 중 오류가 발생했습니다: {str(e)}")
    
    def on_container_changed(self, container_name):
        """버킷 선택 변경"""
        if container_name:
            self.current_container = container_name
            self.current_path = ""  # 새 버킷 선택 시 경로 초기화
            self.update_path_display()
            self.refresh_files()
    
    def refresh_files(self):
        """파일 목록 새로고침"""
        if not self.current_container:
            print("선택된 버킷이 없음")
            return
        
        print(f"파일 목록 새로고침 시작 - 버킷: {self.current_container}, 경로: {self.current_path}")
        
        try:
            # 상태 메시지 표시
            self.statusBar().showMessage(f"'{self.current_container}' 버킷의 파일 목록을 가져오는 중...")
            
            # 폴더별 오브젝트 목록 조회
            objects = self.client.get_objects_with_prefix(self.current_container, self.current_path)
            parsed_items = self.client.parse_folder_structure(objects, self.current_path)
            
            self.file_list.clear()
            self.select_all_checkbox.setChecked(False)
            
            print(f"가져온 항목 수: {len(parsed_items)}")
            
            if not parsed_items:
                # 빈 폴더인 경우
                item = QListWidgetItem("이 폴더는 비어있습니다.")
                item.setData(Qt.ItemDataRole.UserRole, None)
                item.setSizeHint(QWidget().sizeHint())  # 기본 크기 사용
                self.file_list.addItem(item)
                self.statusBar().showMessage(f"'{self.current_container}' 버킷의 현재 폴더가 비어있습니다.")
            else:
                for item_data in parsed_items:
                    print(f"항목 추가: {item_data}")
                    
                    # 리스트 아이템 생성
                    list_item = QListWidgetItem()
                    list_item.setData(Qt.ItemDataRole.UserRole, item_data)
                    
                    # 체크박스가 있는 커스텀 위젯 생성
                    item_widget = self.create_file_item_widget(item_data)
                    
                    # 리스트 아이템 크기 설정
                    list_item.setSizeHint(item_widget.sizeHint())
                    
                    # 리스트에 추가
                    self.file_list.addItem(list_item)
                    self.file_list.setItemWidget(list_item, item_widget)
                
                self.statusBar().showMessage(f"'{self.current_container}' 버킷에서 {len(parsed_items)}개의 항목을 찾았습니다.")
            
            # 경로 표시 업데이트
            self.update_path_display()
                
        except Exception as e:
            print(f"파일 목록 새로고침 오류: {str(e)}")
            import traceback
            traceback.print_exc()
            
            self.statusBar().showMessage("파일 목록을 가져오는 중 오류가 발생했습니다.")
            QMessageBox.critical(self, "오류", f"파일 목록을 가져오는 중 오류가 발생했습니다: {str(e)}")
            
            # 오류 시에도 빈 목록 메시지 표시
            self.file_list.clear()
            item = QListWidgetItem("파일 목록을 가져올 수 없습니다.")
            item.setData(Qt.ItemDataRole.UserRole, None)
            self.file_list.addItem(item)
    
    def create_file_item_widget(self, item_data):
        """체크박스가 있는 파일 항목 위젯 생성"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)  # 여백 증가
        
        # 다크모드 감지
        is_dark = self.is_dark_mode()
        
        # 체크박스
        checkbox = QCheckBox()
        checkbox.stateChanged.connect(self.update_selected_items_display)  # 체크박스 변경 시 표시 업데이트
        widget.checkbox = checkbox  # 위젯에 체크박스 참조 저장
        layout.addWidget(checkbox)
        
        # 아이콘과 이름
        if item_data['type'] == 'folder':
            icon_text = "📁"
        else:
            icon_text = "📄"
        
        icon_label = QLabel(icon_text)
        icon_label.setMinimumSize(24, 24)  # 아이콘 크기 고정
        layout.addWidget(icon_label)
        
        name_label = QLabel(item_data['name'])
        name_label.setMinimumHeight(24)  # 최소 높이 설정
        # 다크모드에 따른 텍스트 색상 설정
        if is_dark:
            name_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 13px;")
        else:
            name_label.setStyleSheet("color: #000000; font-weight: bold; font-size: 13px;")
        layout.addWidget(name_label)
        
        layout.addStretch()
        
        # 크기 정보 (파일인 경우)
        if item_data['type'] == 'file' and item_data.get('bytes', 0) > 0:
            size_text = self.client.format_file_size(item_data['bytes'])
            size_label = QLabel(size_text)
            size_label.setMinimumHeight(24)  # 최소 높이 설정
            if is_dark:
                size_label.setStyleSheet("color: #cccccc; font-size: 11px;")
            else:
                size_label.setStyleSheet("color: #666666; font-size: 11px;")
            layout.addWidget(size_label)
        
        # 위젯 크기 설정
        widget.setMinimumHeight(40)  # 아이템 최소 높이 설정
        widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        
        # 위젯 전체 배경 설정
        if is_dark:
            widget.setStyleSheet("""
                QWidget {
                    background-color: transparent;
                    min-height: 40px;
                }
                QWidget:hover {
                    background-color: #4c4c4c;
                    border-radius: 4px;
                }
            """)
        else:
            widget.setStyleSheet("""
                QWidget {
                    background-color: transparent;
                    min-height: 40px;
                }
                QWidget:hover {
                    background-color: #e6f3ff;
                    border-radius: 4px;
                }
            """)
        
        return widget
    
    def select_file_for_upload(self):
        """업로드할 파일(들) 선택 - 여러 파일 선택 지원"""
        file_paths, _ = QFileDialog.getOpenFileNames(self, "업로드할 파일 선택 (여러 선택 가능)")
        
        if file_paths:
            self.selected_file_paths = file_paths
            
            if len(file_paths) == 1:
                # 단일 파일 선택
                self.selected_file_label.setText(f"선택된 파일: {os.path.basename(file_paths[0])}")
            else:
                # 여러 파일 선택
                total_size = sum(os.path.getsize(fp) for fp in file_paths if os.path.exists(fp))
                self.selected_file_label.setText(
                    f"선택된 파일: {len(file_paths)}개 파일 "
                    f"(총 크기: {self.client.format_file_size(total_size)})"
                )
            
            self.upload_file_btn.setEnabled(bool(self.current_container))
    
    def upload_file(self):
        """파일(들) 업로드"""
        if not hasattr(self, 'selected_file_paths') or not self.selected_file_paths or not self.current_container:
            return
        
        if len(self.selected_file_paths) == 1:
            # 단일 파일 업로드 (기존 로직 유지)
            self._upload_single_file(self.selected_file_paths[0])
        else:
            # 여러 파일 업로드
            self._upload_multiple_files(self.selected_file_paths)
    
    def _upload_single_file(self, file_path):
        """단일 파일 업로드"""
        object_name = os.path.basename(file_path)
        
        # 업로드될 전체 경로 표시
        full_upload_path = f"{self.current_path}{object_name}" if self.current_path else object_name
        
        # 파일명 변경 옵션
        new_name, ok = QInputDialog.getText(
            self, "파일명 확인", 
            f"업로드할 파일명을 확인하세요:\n\n"
            f"버킷: {self.current_container}\n"
            f"전체 경로: /{full_upload_path}\n\n"
            f"파일명:", 
            text=object_name
        )
        
        if not ok:
            return
        
        # 최종 오브젝트 이름 구성
        if self.current_path:
            final_object_name = f"{self.current_path}{new_name}"
        else:
            final_object_name = new_name
        
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"업로드 중... ({final_object_name})")
        
        self.upload_thread = UploadThread(
            self.client, 
            self.current_container, 
            final_object_name, 
            file_path
        )
        self.upload_thread.progress.connect(self.progress_bar.setValue)
        self.upload_thread.finished.connect(self.on_upload_finished)
        self.upload_thread.start()
        
        self.upload_file_btn.setEnabled(False)
    
    def _upload_multiple_files(self, file_paths):
        """여러 파일 업로드 (압축 옵션 포함)"""
        # 업로드 확인 대화상자
        total_files = len(file_paths)
        total_size = sum(os.path.getsize(fp) for fp in file_paths if os.path.exists(fp))
        
        file_list = "\n".join([f"• {os.path.basename(fp)}" for fp in file_paths[:10]])
        if total_files > 10:
            file_list += f"\n... 및 {total_files - 10}개 추가 파일"
        
        # 압축 업로드 옵션 문의 (파일이 5개 이상이거나 총 크기가 100MB 이상일 때 권장)
        should_recommend_compression = total_files >= 5 or total_size >= 100 * 1024 * 1024
        
        if should_recommend_compression:
            reply = QMessageBox.question(
                self, "업로드 방식 선택",
                f"다음 {total_files}개 파일을 업로드합니다.\n"
                f"총 크기: {self.client.format_file_size(total_size)}\n"
                f"업로드 위치: {self.current_container}/{self.current_path}\n\n"
                f"파일 수가 많거나 크기가 큰 경우 압축하여 업로드하는 것이 더 빠를 수 있습니다.\n\n"
                f"압축하여 업로드하시겠습니까?\n\n"
                f"파일 목록:\n{file_list}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Cancel:
                return
            elif reply == QMessageBox.StandardButton.Yes:
                # 압축 업로드
                self._upload_files_compressed(file_paths, [])
                return
        else:
            reply = QMessageBox.question(
                self, "여러 파일 업로드 확인",
                f"다음 {total_files}개 파일을 업로드하시겠습니까?\n"
                f"총 크기: {self.client.format_file_size(total_size)}\n"
                f"업로드 위치: {self.current_container}/{self.current_path}\n\n"
                f"파일 목록:\n{file_list}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # 개별 파일 업로드 (기존 로직)
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"여러 파일 업로드 중... (0/{total_files})")
        
        self.multi_upload_thread = MultiFileUploadThread(
            self.client,
            self.current_container,
            file_paths,
            self.current_path
        )
        self.multi_upload_thread.progress.connect(self.progress_bar.setValue)
        self.multi_upload_thread.finished.connect(self.on_multi_upload_finished)
        self.multi_upload_thread.start()
        
        self.upload_file_btn.setEnabled(False)
    
    def reset_upload_ui(self):
        """업로드 UI 초기화"""
        # 선택된 파일들 초기화
        if hasattr(self, 'selected_file_paths'):
            delattr(self, 'selected_file_paths')
        if hasattr(self, 'selected_folder_path'):
            delattr(self, 'selected_folder_path')
        
        # UI 라벨 초기화
        self.selected_file_label.setText("선택된 파일: 없음")
        self.selected_folder_label.setText("선택된 폴더: 없음")
        
        # 업로드 버튼 비활성화
        self.upload_file_btn.setEnabled(False)
        self.upload_folder_btn.setEnabled(False)
        
        # 진행률 바 및 라벨 초기화
        self.progress_bar.setValue(0)
        self.progress_label.setText("대기 중")
        
        print("업로드 UI 초기화 완료")
    
    def on_multi_upload_finished(self, success, message):
        """여러 파일 업로드 완료"""
        self.progress_label.setText(message)
        self.upload_file_btn.setEnabled(True)
        
        if success:
            self.progress_bar.setValue(100)
            # 업로드 성공 시 파일 목록 자동 새로고침
            print("여러 파일 업로드 성공 - 파일 목록 새로고침")
            self.refresh_files()
            # UI 초기화
            self.reset_upload_ui()
            QMessageBox.information(self, "업로드 완료", message)
        else:
            QMessageBox.warning(self, "업로드 부분 실패", message)
    
    def on_upload_finished(self, success, message):
        """단일 파일 업로드 완료"""
        self.progress_label.setText(message)
        self.upload_file_btn.setEnabled(True)
        
        if success:
            self.progress_bar.setValue(100)
            # 업로드 성공 시 파일 목록 자동 새로고침
            print("단일 파일 업로드 성공 - 파일 목록 새로고침")
            self.refresh_files()
            # UI 초기화
            self.reset_upload_ui()
            QMessageBox.information(self, "업로드 완료", message)
        else:
            QMessageBox.critical(self, "업로드 실패", message)
    
    def download_selected_items(self):
        """선택된 항목들 다운로드"""
        selected_items = self.get_selected_items()
        
        if not selected_items:
            QMessageBox.warning(self, "경고", "다운로드할 항목을 선택하세요.")
            return
        
        # 다운로드 폴더 선택
        download_path = QFileDialog.getExistingDirectory(self, "다운로드할 위치 선택")
        
        if not download_path:
            return
        
        self.progress_bar.setValue(0)
        self.progress_label.setText("다운로드 중...")
        
        self.multi_download_thread = MultiFileDownloadThread(
            self.client,
            self.current_container,
            selected_items,
            download_path
        )
        self.multi_download_thread.progress.connect(self.progress_bar.setValue)
        self.multi_download_thread.finished.connect(self.on_multi_download_finished)
        self.multi_download_thread.start()
    
    def on_multi_download_finished(self, success, message):
        """다중 다운로드 완료"""
        self.progress_label.setText(message)
        
        if success:
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "다운로드 완료", message)
        else:
            QMessageBox.critical(self, "다운로드 실패", message)
    
    def delete_selected_items(self):
        """선택된 항목들 삭제"""
        selected_items = self.get_selected_items()
        
        if not selected_items:
            QMessageBox.warning(self, "경고", "삭제할 항목을 선택하세요.")
            return
        
        item_names = [item['name'] for item in selected_items]
        reply = QMessageBox.question(
            self, "항목 삭제",
            f"다음 {len(selected_items)}개 항목을 삭제하시겠습니까?\n\n" + "\n".join(item_names),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                failed_items = []
                
                for item in selected_items:
                    if item['type'] == 'file':
                        # 파일 삭제
                        success = self.client.delete_object(self.current_container, item['full_path'])
                    else:
                        # 폴더 삭제 (폴더 내 모든 파일 삭제)
                        success = self.delete_folder(item['full_path'])
                    
                    if not success:
                        failed_items.append(item['name'])
                
                if failed_items:
                    QMessageBox.warning(self, "삭제 실패", f"다음 항목들의 삭제에 실패했습니다:\n" + "\n".join(failed_items))
                else:
                    QMessageBox.information(self, "삭제 완료", f"{len(selected_items)}개 항목이 삭제되었습니다.")
                
                self.refresh_files()
                
            except Exception as e:
                QMessageBox.critical(self, "오류", f"삭제 중 오류가 발생했습니다: {str(e)}")
    
    def delete_folder(self, folder_path):
        """폴더 삭제 (폴더 내 모든 파일 삭제)"""
        try:
            # 폴더 내 모든 파일 목록 조회
            all_objects = self.client.get_all_objects_in_folder(self.current_container, folder_path)
            
            # 모든 파일 삭제
            for obj in all_objects:
                success = self.client.delete_object(self.current_container, obj['name'])
                if not success:
                    return False
            
            return True
            
        except Exception as e:
            print(f"폴더 삭제 오류: {str(e)}")
            return False

    def check_theme_change(self):
        """테마 변경 감지"""
        current_dark_mode = self.is_dark_mode()
        if current_dark_mode != self.last_dark_mode:
            self.last_dark_mode = current_dark_mode
            self.apply_styles()

    def go_back(self):
        """상위 폴더로 이동"""
        if self.current_path:
            # 현재 경로에서 마지막 폴더 제거
            path_parts = self.current_path.rstrip('/').split('/')
            if len(path_parts) > 1:
                self.current_path = '/'.join(path_parts[:-1]) + '/'
            else:
                self.current_path = ""
            
            self.update_path_display()
            self.refresh_files()
    
    def update_path_display(self):
        """경로 표시 업데이트"""
        display_path = f"/{self.current_path}" if self.current_path else "/"
        self.path_label.setText(f"경로: {display_path}")
        self.back_btn.setEnabled(bool(self.current_path))
        
        # 업로드 위치 표시 업데이트
        upload_path = f"/{self.current_path}" if self.current_path else "/"
        container_name = self.current_container if self.current_container else "선택된 버킷 없음"
        self.upload_path_label.setText(f"업로드 위치: {container_name}{upload_path}")
        
        # 선택된 항목 표시 업데이트
        self.update_selected_items_display()
    
    def update_selected_items_display(self):
        """선택된 항목 표시 업데이트"""
        selected_items = self.get_selected_items()
        if not selected_items:
            self.selected_items_label.setText("선택된 항목: 없음")
        else:
            item_count = len(selected_items)
            file_count = sum(1 for item in selected_items if item['type'] == 'file')
            folder_count = sum(1 for item in selected_items if item['type'] == 'folder')
            
            parts = []
            if file_count > 0:
                parts.append(f"{file_count}개 파일")
            if folder_count > 0:
                parts.append(f"{folder_count}개 폴더")
            
            self.selected_items_label.setText(f"선택된 항목: {', '.join(parts)} (총 {item_count}개)")
    
    def create_folder(self):
        """새 폴더 생성"""
        if not self.current_container:
            QMessageBox.warning(self, "경고", "먼저 버킷을 선택하세요.")
            return
        
        folder_name, ok = QInputDialog.getText(self, "새 폴더", "폴더 이름을 입력하세요:")
        
        if ok and folder_name:
            # 폴더 경로 구성
            if self.current_path:
                folder_path = f"{self.current_path}{folder_name}/"
            else:
                folder_path = f"{folder_name}/"
            
            try:
                # 빈 파일을 업로드해서 폴더 구조 생성
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(b"")  # 빈 파일
                    temp_file_path = temp_file.name
                
                # .keep 파일로 폴더 생성
                keep_file_path = f"{folder_path}.keep"
                
                if self.client.upload_file(self.current_container, keep_file_path, temp_file_path):
                    QMessageBox.information(self, "성공", f"폴더 '{folder_name}'이 생성되었습니다.")
                    self.refresh_files()
                else:
                    QMessageBox.critical(self, "실패", "폴더 생성에 실패했습니다.")
                
                # 임시 파일 삭제
                os.unlink(temp_file_path)
                
            except Exception as e:
                QMessageBox.critical(self, "오류", f"폴더 생성 중 오류가 발생했습니다: {str(e)}")
    
    def on_item_double_clicked(self, item):
        """항목 더블클릭 처리"""
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            return
        
        if item_data.get('type') == 'folder':
            # 폴더인 경우 해당 폴더로 이동
            self.current_path = item_data['full_path']
            if not self.current_path.endswith('/'):
                self.current_path += '/'
            
            self.update_path_display()
            self.refresh_files()
    
    def toggle_select_all(self, state):
        """전체 선택/해제"""
        check_state = Qt.CheckState.Checked if state == Qt.CheckState.Checked.value else Qt.CheckState.Unchecked
        
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            widget = self.file_list.itemWidget(item)
            if widget and hasattr(widget, 'checkbox'):
                widget.checkbox.setCheckState(check_state)
        
        # 선택된 항목 표시 업데이트
        self.update_selected_items_display()
    
    def get_selected_items(self):
        """선택된 항목들 반환"""
        selected_items = []
        
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            widget = self.file_list.itemWidget(item)
            
            if widget and hasattr(widget, 'checkbox') and widget.checkbox.isChecked():
                item_data = item.data(Qt.ItemDataRole.UserRole)
                if item_data:
                    selected_items.append(item_data)
        
        return selected_items
    
    def select_folder_for_upload(self):
        """업로드할 폴더 선택"""
        folder_path = QFileDialog.getExistingDirectory(self, "업로드할 폴더 선택")
        
        if folder_path:
            self.selected_folder_path = folder_path
            self.selected_folder_label.setText(f"선택된 폴더: {os.path.basename(folder_path)}")
            self.upload_folder_btn.setEnabled(bool(self.current_container))
    
    def upload_folder(self):
        """폴더 업로드 (압축 옵션 포함)"""
        if not hasattr(self, 'selected_folder_path') or not self.current_container:
            return
        
        folder_name = os.path.basename(self.selected_folder_path)
        
        # 폴더 내용 분석
        total_files = 0
        total_size = 0
        for root, dirs, files in os.walk(self.selected_folder_path):
            total_files += len(files)
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
        
        # 압축 업로드 옵션 문의 (파일이 10개 이상이거나 총 크기가 500MB 이상일 때 권장)
        should_recommend_compression = total_files >= 10 or total_size >= 500 * 1024 * 1024
        
        if should_recommend_compression:
            reply = QMessageBox.question(
                self, "폴더 업로드 방식 선택",
                f"폴더 '{folder_name}'을 업로드합니다.\n"
                f"파일 수: {total_files}개\n"
                f"총 크기: {self.client.format_file_size(total_size)}\n"
                f"업로드 위치: {self.current_container}/{self.current_path}\n\n"
                f"파일 수가 많거나 크기가 큰 경우 압축하여 업로드하는 것이 더 빠를 수 있습니다.\n\n"
                f"압축하여 업로드하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Cancel:
                return
            elif reply == QMessageBox.StandardButton.Yes:
                # 압축 업로드
                self._upload_files_compressed([], [self.selected_folder_path])
                return
        else:
            # 일반 폴더명 확인
            new_name, ok = QInputDialog.getText(
                self, "폴더명 확인",
                f"업로드할 폴더명을 확인하세요:",
                text=folder_name
            )
            
            if not ok:
                return
        
        # 기존 폴더 업로드 로직
        # 업로드할 폴더명 확인
        new_name, ok = QInputDialog.getText(
            self, "폴더명 확인",
            f"업로드할 폴더명을 확인하세요:",
            text=folder_name
        )
        
        if not ok:
            return
        
        # 원격 기본 경로 구성
        remote_base_path = self.current_path + new_name if self.current_path else new_name
        
        self.progress_bar.setValue(0)
        self.progress_label.setText("폴더 업로드 중...")
        
        self.folder_upload_thread = FolderUploadThread(
            self.client,
            self.current_container,
            self.selected_folder_path,
            remote_base_path
        )
        self.folder_upload_thread.progress.connect(self.progress_bar.setValue)
        self.folder_upload_thread.finished.connect(self.on_folder_upload_finished)
        self.folder_upload_thread.start()
        
        self.upload_folder_btn.setEnabled(False)
    
    def on_folder_upload_finished(self, success, message):
        """폴더 업로드 완료"""
        self.progress_label.setText(message)
        self.upload_folder_btn.setEnabled(True)
        
        if success:
            self.progress_bar.setValue(100)
            self.refresh_files()
            # UI 초기화
            self.reset_upload_ui()
            QMessageBox.information(self, "업로드 완료", message)
        else:
            QMessageBox.critical(self, "업로드 실패", message)
    
    def _upload_files_compressed(self, file_paths, folder_paths):
        """파일들과 폴더들을 압축하여 업로드"""
        # 압축 파일명 입력받기
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
        
        # .zip 확장자 확인 및 추가
        zip_filename = zip_filename.strip()
        if not zip_filename.lower().endswith('.zip'):
            zip_filename += '.zip'
        
        # 압축 및 업로드 시작
        self.progress_bar.setValue(0)
        self.progress_label.setText("압축 파일 생성 중...")
        
        self.compressed_upload_thread = CompressedUploadThread(
            self.client,
            self.current_container,
            file_paths,
            folder_paths,
            self.current_path,
            zip_filename
        )
        
        # 시그널 연결
        self.compressed_upload_thread.progress.connect(self.progress_bar.setValue)
        self.compressed_upload_thread.status.connect(self.progress_label.setText)
        self.compressed_upload_thread.finished.connect(self.on_compressed_upload_finished)
        self.compressed_upload_thread.start()
        
        # 업로드 버튼 비활성화
        self.upload_file_btn.setEnabled(False)
        self.upload_folder_btn.setEnabled(False)
    
    def on_compressed_upload_finished(self, success, message):
        """압축 업로드 완료"""
        self.upload_file_btn.setEnabled(True)
        self.upload_folder_btn.setEnabled(True)
        
        if success:
            self.progress_bar.setValue(100)
            # 업로드 성공 시 파일 목록 자동 새로고침
            print("압축 업로드 성공 - 파일 목록 새로고침")
            self.refresh_files()
            # UI 초기화
            self.reset_upload_ui()
            QMessageBox.information(self, "압축 업로드 완료", message)
        else:
            QMessageBox.critical(self, "압축 업로드 실패", message)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("네이버 클라우드 Archive Storage 관리자")
    
    window = NaverArchiveStorageGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main() 