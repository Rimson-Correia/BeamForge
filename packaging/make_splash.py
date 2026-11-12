"""Write the still start-up picture to a PNG file: python make_splash.py OUTPUT.png"""

import sys

from PySide6.QtWidgets import QApplication

from beamforge.gui import splash

app = QApplication([])
if not splash.still_image().save(sys.argv[1], "PNG"):
    raise SystemExit("could not write the start-up picture")
