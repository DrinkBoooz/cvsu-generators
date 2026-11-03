# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = [
    'pycparser.lextab',
    'pycparser.yacctab',
    'ceit_generator',
    'attendancegen',
    'grading_generator',
    'generic_doc_generator',
]
hiddenimports += collect_submodules('modules')
hiddenimports += collect_submodules('pypdf')

a = Analysis(
    ['main.py'],
    pathex=['..'],
    binaries=[],
    datas=[
        ('ui.html', '.'),
        ('css', 'css'),
        ('js', 'js'),
        ('../templates', 'templates'),
        ('../attendance', 'attendance'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CvSU Gen',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
    icon=['app_icon.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CvSU Gen',
)
