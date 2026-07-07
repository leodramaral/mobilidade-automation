# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

streamlit_datas, streamlit_binaries, streamlit_hiddenimports = collect_all('streamlit')
altair_datas, altair_binaries, altair_hiddenimports = collect_all('altair')
pandas_datas, pandas_binaries, pandas_hiddenimports = collect_all('pandas')

a = Analysis(
    ['run_dashboard.py'],
    pathex=['.'],
    binaries=streamlit_binaries + altair_binaries + pandas_binaries,
    datas=[
        ('config.json', '.'),
        ('ui', 'ui'),
        ('automacoes', 'automacoes'),
        ('persistencia', 'persistencia'),
        ('modelos', 'modelos'),
        ('coletor.py', '.'),
        ('.streamlit', '.streamlit'),
    ] + streamlit_datas + altair_datas + pandas_datas,
    hiddenimports=[
        'coletor',
        'automacoes.automacao_99',
        'automacoes.base',
        'persistencia.repositorio_banco',
        'persistencia.base',
        'modelos.corrida',
        'selenium',
        'appium',
    ] + streamlit_hiddenimports + altair_hiddenimports + pandas_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Mobilidade',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
)
