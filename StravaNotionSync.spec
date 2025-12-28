# -*- mode: python ; coding: utf-8 -*-
# Ce fichier a été généré par pyi-makespec

# --- Configuration de l'analyse (a) ---
a = Analysis(
    ['gui.py'],
    pathex=['C:\\Users\\maxif\\Documents\\Projets\\API_Strava--Notion'], # VÉRIFIEZ LE CHEMIN, C'EST LE VÔTRE
    
    # FICHIERS ET DOSSIERS À INCLURE DANS LE BUNDLE FINAL
    datas=[
        ('.env', '.'),        # Copie le fichier .env 
        ('models', 'models')  # Copie tout le dossier de votre logique 'models'
    ],
    
    # IMPORTS CACHÉS : Tous vos modules locaux que PyInstaller doit trouver
    hiddenimports=[
        'models.config_manager', 
        'models.ngrok_manager',     
        'models.notion_client',     
        'models.polling_scheduler', 
        'models.strava_client', 
        'models.server_manager'
    ],
    
    # Autres paramètres standard
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    cipher=None,
    key=None,
    binaries=[],
)

# --- Configuration des fichiers de support (pyz) ---
pyz = PYZ(a.pure, a.zipped_data)

# --- Configuration de la bibliothèque (exe) ---
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='StravaNotionSync',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,     
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# --- Configuration du fichier unique (coll) ---
# Ceci est pour le mode --onefile que nous utilisons pour simplifier l'installeur
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='StravaNotionSync',
)