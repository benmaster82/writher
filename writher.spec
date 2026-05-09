# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for WritHer."""

import os
import sys
import customtkinter
import faster_whisper

block_cipher = None

# CustomTkinter assets path
ctk_path = os.path.dirname(customtkinter.__file__)

# faster_whisper assets (Silero VAD model)
fw_path = os.path.dirname(faster_whisper.__file__)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # CustomTkinter theme assets (required for CTk widgets to render)
        (ctk_path, 'customtkinter'),
        # faster_whisper assets (Silero VAD ONNX models)
        (os.path.join(fw_path, 'assets'), os.path.join('faster_whisper', 'assets')),
        # Pre-generated brand icons (avoids writing to _internal at runtime)
        ('writher.ico', '.'),
        ('writher_icon.png', '.'),
        # Logo image
        ('img', 'img'),
    ],
    hiddenimports=[
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'PIL._tkinter_finder',
        'customtkinter',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy ML frameworks not needed by WritHer
        'torch', 'torchvision', 'torchaudio', 'torch.distributed',
        'tensorflow', 'tensorboard', 'tf_keras', 'keras',
        'scipy', 'matplotlib', 'pandas', 'sklearn', 'scikit-learn',
        'pytest', 'IPython', 'notebook', 'jupyter',
        'lxml', 'pygments', 'cv2', 'opencv',
        'transformers', 'datasets', 'accelerate',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WritHer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,          # Debug mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='writher.ico',     # Pandora Blackboard eyes icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WritHer',
)
