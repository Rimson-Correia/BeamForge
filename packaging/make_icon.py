"""Write the application icon to an .ico file: python make_icon.py OUTPUT.ico"""

import sys

from PySide6.QtWidgets import QApplication

from beamforge.gui import theme

app = QApplication([])
if not theme.app_icon().pixmap(256, 256).save(sys.argv[1], "ICO"):
    raise SystemExit("could not write the icon")
