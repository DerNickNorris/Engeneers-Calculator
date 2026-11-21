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
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "resources" / "icon.png")))
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Ingenieurs-Rechner")
    apply_theme(app)
    win = MainWindow()
    win.show()
    # Projektdatei per Doppelklick / Kommandozeile öffnen
    if len(argv) > 1 and argv[1].lower().endswith(".irp"):
        win.open_project(argv[1])
    return app.exec()


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
    lines.append(f"{len(classes)} Rechner – {'bestanden' if ok else 'FEHLER'}")
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
