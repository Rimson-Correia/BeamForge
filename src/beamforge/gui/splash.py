"""Start-up screen: logo, name, tag line and an animated loading bar."""

from __future__ import annotations

import math

from PySide6.QtCore import QElapsedTimer, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from beamforge import __version__
from beamforge.gui import theme

TAGLINE = "Engineer your beam. Master your fluence."
WIDTH, HEIGHT = 580, 350
PERIOD_MS = 1500  # one back-and-forth sweep of the loading bar
TRACK = QRectF((WIDTH - 220) / 2, 282, 220, 4)
SEGMENT_WIDTH = 90


def _font(pixels: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont("Segoe UI")
    font.setPixelSize(pixels)
    font.setWeight(weight)
    return font


def paint(painter: QPainter, phase: float | None) -> None:
    """Paint the start-up screen at WIDTH x HEIGHT.

    ``phase`` (0 to 1) is the position in the loading-bar cycle. ``None`` draws
    the still picture, with an empty loading bar.
    """
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    background = QLinearGradient(0, 0, WIDTH, HEIGHT)
    background.setColorAt(0.0, QColor("#0b1220"))
    background.setColorAt(1.0, QColor(theme.ACCENT_DARK))
    painter.fillRect(0, 0, WIDTH, HEIGHT, background)

    theme.draw_logo(painter, QRectF((WIDTH - 92) / 2, 44, 92, 92))

    centre = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
    painter.setPen(QColor("#ffffff"))
    painter.setFont(_font(34, QFont.Weight.DemiBold))
    painter.drawText(QRectF(0, 150, WIDTH, 50), centre, "BeamForge")
    painter.setPen(QColor("#bfdbfe"))
    painter.setFont(_font(16))
    painter.drawText(QRectF(0, 204, WIDTH, 30), centre, TAGLINE)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 45))
    painter.drawRoundedRect(TRACK, 2, 2)
    if phase is not None:
        travel = TRACK.width() - SEGMENT_WIDTH
        x = TRACK.left() + travel * (0.5 - 0.5 * math.cos(2 * math.pi * phase))
        glow = QLinearGradient(x, 0, x + SEGMENT_WIDTH, 0)
        glow.setColorAt(0.0, QColor(147, 197, 253, 0))
        glow.setColorAt(0.5, QColor(255, 255, 255))
        glow.setColorAt(1.0, QColor(147, 197, 253, 0))
        painter.setBrush(glow)
        painter.drawRoundedRect(QRectF(x, TRACK.top(), SEGMENT_WIDTH, TRACK.height()), 2, 2)

    painter.setPen(QColor(255, 255, 255, 130))
    painter.setFont(_font(12))
    painter.drawText(QRectF(0, 300, WIDTH, 24), centre, f"Version {__version__}")


def still_image() -> QImage:
    """The start-up screen as a still picture (shown while the Windows exe unpacks)."""
    image = QImage(WIDTH, HEIGHT, QImage.Format.Format_RGB32)
    painter = QPainter(image)
    paint(painter, None)
    painter.end()
    return image


class Splash(QWidget):
    """Frameless start-up window with an animated loading bar."""

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(WIDTH, HEIGHT)
        self._clock = QElapsedTimer()
        self._clock.start()
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def show_centred(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.geometry()
            self.move(area.center().x() - WIDTH // 2, area.center().y() - HEIGHT // 2)
        self.show()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt name)
        painter = QPainter(self)
        paint(painter, (self._clock.elapsed() % PERIOD_MS) / PERIOD_MS)
        painter.end()
