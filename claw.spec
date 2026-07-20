# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for claw.exe — 单文件控制台应用。"""

import sys
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent

# ---- 收集所有隐式依赖 --------------------------------------------------
hidden_imports = [
    # openai SDK
    "openai",
    "httpx",
    "httpcore",
    "hpack",
    "h2",
    # anthropic SDK
    "anthropic",
    # rich
    "rich",
    "rich.console",
    "rich.panel",
    "rich.markdown",
    "rich.table",
    "rich.rule",
    "rich.text",
    "rich.syntax",
    "rich.theme",
    "rich.style",
    "rich.color",
    "rich.box",
    "rich.align",
    "rich.padding",
    # flask (feishu bot)
    "flask",
    "werkzeug",
    "jinja2",
    "markupsafe",
    "itsdangerous",
    "click",
    "blinker",
    # dotenv
    "dotenv",
    # requests
    "requests",
    "urllib3",
    "certifi",
    "charset_normalizer",
    "idna",
    # misc
    "json",
    "logging",
    "hashlib",
    "threading",
    "subprocess",
    "readline",
]

# ---- 收集 claw 包的所有子模块 --------------------------------------------
claw_dir = ROOT / "claw"
claw_packages = []
for py_file in claw_dir.rglob("*.py"):
    if py_file.name == "__init__.py":
        continue
    rel = py_file.relative_to(ROOT).with_suffix("")
    mod_name = ".".join(rel.parts)
    claw_packages.append(mod_name)

# ---- PyInstaller Analysis ------------------------------------------------
a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # 嵌入 claw 包所有 .py 文件
        (str(ROOT / "claw"), "claw"),
    ],
    hiddenimports=hidden_imports + claw_packages,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
        "cv2",
        "tensorflow",
        "torch",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# ---- 过滤掉不必要的二进制文件 -------------------------------------------
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# ---- 单文件 EXE ---------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="claw",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 控制台应用——双击打开 CMD 窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "claw.ico") if (ROOT / "claw.ico").exists() else None,
)
