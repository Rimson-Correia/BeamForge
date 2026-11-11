"""Start the desktop application: ``beamforge-gui [setup.toml]``."""

from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from beamforge.gui import theme
from beamforge.gui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="beamforge-gui", description="BeamForge desktop app.")
    parser.add_argument("setup", nargs="?", help="TOML setup file to open")
    parser.add_argument(
        "--screenshot", metavar="PNG", help="save a picture of the window and exit (for testing)"
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("BeamForge")
    app.setStyle("Fusion")
    app.setStyleSheet(theme.style_sheet())
    window = MainWindow()
    if args.setup:
        window.load_file(args.setup)
    window.show()
    if args.screenshot:

        def capture() -> None:
            window.grab().save(args.screenshot)
            app.quit()

        QTimer.singleShot(800, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
