"""Start the desktop application: ``beamforge-gui [setup.toml]``."""

from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from beamforge.gui import theme
from beamforge.gui.main_window import MainWindow
from beamforge.gui.splash import Splash

SPLASH_MS = 2400  # how long the animated start-up screen stays


def _close_unpacking_picture() -> None:
    """Close the still picture the Windows exe shows while it unpacks, if any."""
    try:
        import pyi_splash  # provided by PyInstaller, only inside the exe
    except ImportError:
        return
    pyi_splash.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="beamforge-gui", description="BeamForge desktop app.")
    parser.add_argument("setup", nargs="?", help="TOML setup file to open")
    parser.add_argument("--no-splash", action="store_true", help="skip the start-up screen")
    parser.add_argument(
        "--screenshot", metavar="PNG", help="save a picture of the window and exit (for testing)"
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("BeamForge")
    app.setWindowIcon(theme.app_icon())
    app.setStyle("Fusion")
    app.setStyleSheet(theme.style_sheet())

    splash = None
    if not (args.no_splash or args.screenshot):
        splash = Splash()
        splash.show_centred()
        app.processEvents()
    _close_unpacking_picture()

    window = MainWindow()
    if args.setup:
        window.load_file(args.setup)

    if splash is None:
        window.show()
    else:

        def reveal() -> None:
            window.show()
            splash.close()

        QTimer.singleShot(SPLASH_MS, reveal)
    if args.screenshot:

        def capture() -> None:
            window.grab().save(args.screenshot)
            app.quit()

        QTimer.singleShot(800, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
