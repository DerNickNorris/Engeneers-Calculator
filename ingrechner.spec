# PyInstaller-Spezifikation: erzeugt dist/Ingenieurs-Rechner/Ingenieurs-Rechner.exe
# Aufruf (unter Windows):  pyinstaller ingrechner.spec --noconfirm
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Rechenmodule werden zur Laufzeit automatisch gefunden -> explizit mitnehmen.
# (direkt aus dem Dateisystem, damit jedes neue Modul ohne Spec-Änderung im Build landet)
root = Path("ingrechner/calculators")
hidden = sorted(
    ".".join(("ingrechner", "calculators", *p.relative_to(root).with_suffix("").parts)).removesuffix(".__init__")
    for p in root.rglob("*.py")
)

a = Analysis(
    ["run.py"],
    pathex=["."],
    datas=[("ingrechner/resources", "ingrechner/resources"),
           *collect_data_files("pint", excludes=["**/testsuite/**"]),
           *collect_data_files("faster_whisper")],          # Sprachaktivitätserkennung (silero_vad.onnx)
    binaries=[*collect_dynamic_libs("ctranslate2"), *collect_dynamic_libs("onnxruntime")],
    hiddenimports=[*hidden, "PySide6.QtMultimedia"],
    excludes=[
        "tkinter", "lxml", "pytest", "_pytest", "pandas", "scipy", "IPython", "pint.testsuite",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
        "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml",
        "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    ],
    noarchive=False,
)
# Nicht benötigte Qt-Teile (QML/Quick, PDF-Viewer, Sprachdateien außer de/en) entfernen
DROP = ("Qt6Qml", "Qt6Quick", "Qt6Pdf", "Qt6VirtualKeyboard", "Qt6OpenGL", "Qt6Network",
        "qpdf", "qtvirtualkeyboard", "qmltooling")


def keep(entry) -> bool:
    name = entry[0].replace("\\", "/")
    if any(d.lower() in name.lower() for d in DROP):
        return False
    if "/translations/" in name and not any(f"_{lang}." in name for lang in ("de", "en")):
        return False
    return True


a.binaries = [b for b in a.binaries if keep(b)]
a.datas = [d for d in a.datas if keep(d)]

pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Ingenieurs-Rechner",
    icon="ingrechner/resources/icon.ico",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Ingenieurs-Rechner", upx=False)
