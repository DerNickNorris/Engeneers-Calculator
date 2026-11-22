"""Einstiegspunkt der Desktop-App."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    if "--selftest" in argv:
        return selftest()
    import matplotlib

    matplotlib.use("QtAgg")
    from PySide6.QtWidgets import QApplication

    from ingrechner import APP_NAME
    from ingrechner.gui.main_window import MainWindow
    from ingrechner.gui.theme import apply_theme

    from pathlib import Path

    from PySide6.QtGui import QIcon

    if sys.platform == "win32":  # eigenes Taskleisten-Symbol statt python.exe
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ingrechner.desktop")

    app = QApplication(argv)
    from ingrechner.gui import errors

    errors.install()   # Fehler sichtbar machen (die .exe hat kein Konsolenfenster)
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "resources" / "icon.png")))
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Ingenieurs-Rechner")
    apply_theme(app)
    win = MainWindow(check_updates=True)
    win.show()
    # Projekt- oder Protokolldatei per Doppelklick / Kommandozeile öffnen
    files = [a for a in argv[1:] if not a.startswith("--")]
    if files:
        win.open_file(files[0])
    return app.exec()


def _report_ok() -> bool:
    """Erzeugt testweise einen Gesamtbericht mit zwei Positionen (ohne Skizzen)."""
    import tempfile
    from pathlib import Path

    from ingrechner.core import registry
    from ingrechner.core.project import Project
    from ingrechner.core.project_report import build_project_report

    p = Project()
    p.add_position("mb.biegung_einfeldtraeger", {}, titel="Selbsttest")
    p.add_position("fl.u_wert", {})
    with tempfile.TemporaryDirectory() as tmp:
        out = build_project_report(Path(tmp) / "selbsttest.pdf", p, registry.by_id())
        return out.read_bytes()[:4] == b"%PDF"


def _multimedia_ok(lines: list[str]) -> bool:
    """Lädt Qt Multimedia und dessen Plugins wie beim Diktat.

    Fehlende Bibliotheken im Build fallen sonst erst beim Klick auf „Diktat“ auf.
    """
    try:
        from pathlib import Path

        from PySide6.QtCore import QCoreApplication, QLibraryInfo, QPluginLoader
        from PySide6.QtMultimedia import QAudioFormat, QMediaDevices

        app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841 - für QMediaDevices
        plugin_dir = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)) / "multimedia"
        plugins = sorted(p for p in plugin_dir.glob("*") if p.suffix.lower() in (".dll", ".so", ".dylib"))
        loaded = []
        for plugin in plugins:
            loader = QPluginLoader(str(plugin))
            if loader.load():
                loaded.append(plugin.name)
            else:
                lines.append(f"    Plugin {plugin.name} nicht ladbar: {loader.errorString()}")
        n = len(QMediaDevices.audioInputs())
        QAudioFormat()
        lines.append(f"    Multimedia-Plugins geladen: {', '.join(loaded) or 'keine'}; Mikrofone gefunden: {n}")
        return bool(loaded) and len(loaded) == len(plugins)
    except Exception as exc:  # noqa: BLE001
        lines.append(f"    Qt Multimedia nicht ladbar: {exc}")
        return False


def selftest() -> int:
    """Prüft im fertigen Build, dass alle Module gefunden werden und rechnen (für CI)."""
    import io

    from ingrechner.core import registry
    from ingrechner.core.report import plot_png

    classes = registry.discover()
    lines = []
    ok = bool(classes)
    for cls in classes:
        calc = cls()
        res = calc.run({})
        png = plot_png(calc, calc.defaults(), res)
        ok &= res.ok
        lines.append(f"{'OK ' if res.ok else 'ERR'} {cls.id}: {len(res.values)} Werte, Plot={bool(png)}")
    # Phase 2: Werkzeuge
    from ingrechner.core.expr import Evaluator
    from ingrechner.core.materials import MaterialLibrary
    from ingrechner.core.unitconv import convert

    checks = {
        "Formel-Auswerter": abs(Evaluator("deg").evaluate("sqrt(3^2+4^2) + sin(30)")[1] - 5.5) < 1e-12,
        "Einheiten": abs(convert(1, "bar", "psi") - 14.503773773) < 1e-6,
        "Materialdatenbank": len(MaterialLibrary(None).builtin) >= 20,
    }
    # Phase 3: Protokolle und Spracherkennung
    from ingrechner.core import speech
    from ingrechner.core.protocols import Protocol, TemplateLibrary

    checks["Protokollvorlagen"] = bool(Protocol.new(TemplateLibrary(None).get("b:baubesprechung")).values)
    checks["Gesamtbericht"] = _report_ok()
    checks["Spracherkennung installiert"] = speech.available()
    checks["Mikrofon-Modul (Qt Multimedia)"] = _multimedia_ok(lines)
    model = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--selftest-model=")), None)
    if model:  # optional: echte Erkennung mit Testaudio (--selftest-audio=...)
        audio = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--selftest-audio=")), None)
        text = speech.SpeechEngine(model).transcribe(audio) if audio else ""
        lines.append(f"    Erkannt: {text!r}")
        checks["Spracherkennung mit Modell"] = bool(text.strip())
    for name, passed in checks.items():
        ok &= passed
        lines.append(f"{'OK ' if passed else 'ERR'} {name}")
    lines.append(f"{len(classes)} Rechner, {len(checks)} Werkzeug-Prüfungen – {'bestanden' if ok else 'FEHLER'}")
    text = "\n".join(lines)
    try:
        print(text)
    except (AttributeError, OSError):  # GUI-Build ohne Konsole
        pass
    out = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--selftest-out=")), None)
    if out:
        with io.open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
