#!/usr/bin/env python3
import os
import sys
import platform
import subprocess
import shutil

def get_platform_name():
    system = platform.system().lower()
    if system == 'windows':
        return 'windows'
    elif system == 'darwin':
        return 'macos'
    elif system == 'linux':
        return 'ubuntu'
    else:
        return system

def install_dependencies():
    print("Installing dependencies...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)

def create_spec_file():
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

import os
import sys

a = Analysis(
    ['integrated_storage_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui', 
        'PyQt6.QtWidgets',
        'boto3',
        'botocore',
        'requests',
        'urllib3',
        'requests_toolbelt',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='NCP_Storage_Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
'''
    
    if platform.system() == 'Darwin':
        spec_content += '''
app = BUNDLE(
    exe,
    name='NCP Storage Manager.app',
    icon=None,
    bundle_identifier='com.ncp.storage.manager',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '10.13.0',
    },
)
'''
    
    with open('ncp_storage_manager.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)

def build_executable():
    platform_name = get_platform_name()
    build_dir = os.path.join('build', platform_name)
    
    print(f"Building for {platform_name}...")
    
    os.makedirs(build_dir, exist_ok=True)
    
    create_spec_file()
    
    cmd = [
        'pyinstaller',
        '--clean',
        '--noconfirm',
        f'--distpath={build_dir}',
        'ncp_storage_manager.spec'
    ]
    
    subprocess.run(cmd, check=True)
    
    print(f"Build completed for {platform_name}")
    print(f"Output directory: {build_dir}")
    
    if os.path.exists('ncp_storage_manager.spec'):
        os.remove('ncp_storage_manager.spec')

def clean_build():
    print("Cleaning previous builds...")
    dirs_to_clean = ['build', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    
    files_to_clean = ['*.spec']
    for pattern in files_to_clean:
        for file in os.listdir('.'):
            if file.endswith('.spec'):
                os.remove(file)

def main():
    if '--clean' in sys.argv:
        clean_build()
        return
    
    try:
        print("NCP Storage Manager - Cross-platform Build Script")
        print(f"Platform: {get_platform_name()}")
        print(f"Python: {sys.version}")
        print("=" * 50)
        
        install_dependencies()
        build_executable()
        
        print("=" * 50)
        print("Build completed successfully!")
        
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 