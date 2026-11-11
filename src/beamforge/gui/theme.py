"""Colours, style sheet and application icon."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDir, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)

ACCENT = "#2563eb"
ACCENT_DARK = "#1e3a8a"
TEXT = "#1f2937"
MUTED = "#64748b"
BORDER = "#e3e7ee"
AMBER = "#f59e0b"

STYLE = f"""
QWidget {{ font-family: "Segoe UI"; font-size: 10pt; color: {TEXT}; }}
QMainWindow, QWidget#root, QWidget#inputs {{ background: #f4f6f9; }}
QScrollArea {{ border: none; background: #f4f6f9; }}

QGroupBox {{
    background: #ffffff; border: 1px solid {BORDER}; border-radius: 10px;
    margin-top: 6px; padding: 36px 12px 8px 12px; font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: padding; subcontrol-position: top left;
    left: 12px; top: 11px; color: {ACCENT_DARK};
}}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
QScrollBar::handle {{ background: #cbd5e1; border-radius: 3px; min-height: 30px; min-width: 30px; }}
QScrollBar::handle:hover {{ background: #94a3b8; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QToolBar::separator {{ background: {BORDER}; width: 1px; margin: 6px 8px; }}
QGroupBox * {{ font-weight: 400; }}

QLineEdit, QComboBox {{
    background: #ffffff; border: 1px solid #cfd6e0; border-radius: 6px;
    padding: 5px 8px; min-height: 18px; selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QLineEdit[invalid="true"] {{ border: 1px solid #dc2626; background: #fef2f2; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QLabel[role="unit"] {{ color: {MUTED}; }}

QFrame#card {{ background: #ffffff; border: 1px solid {BORDER}; border-radius: 10px; }}
QLabel#cardTitle {{ color: {MUTED}; font-size: 9pt; font-weight: 600; }}
QLabel#cardValue {{ color: #0f172a; font-size: 19pt; font-weight: 600; }}
QLabel#cardSub {{ color: {MUTED}; font-size: 9pt; }}

QTableWidget {{
    background: #ffffff; border: 1px solid {BORDER}; border-radius: 10px;
    gridline-color: #eef1f5; alternate-background-color: #f8fafc;
    selection-background-color: #dbeafe; selection-color: {TEXT};
}}
QHeaderView::section {{
    background: #f1f4f8; border: none; border-bottom: 1px solid {BORDER};
    padding: 6px 8px; font-weight: 600; color: #475569;
}}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 10px; background: #ffffff; }}
QTabBar::tab {{
    padding: 7px 16px; margin-right: 2px; color: {MUTED};
    border: none; border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {ACCENT_DARK}; border-bottom: 2px solid {ACCENT}; font-weight: 600;
}}

QToolBar {{ background: #ffffff; border: none; border-bottom: 1px solid {BORDER};
    spacing: 4px; padding: 5px 8px; }}
QToolButton {{ padding: 6px 12px; border-radius: 6px; }}
QToolButton:hover {{ background: #eef2ff; color: {ACCENT_DARK}; }}
QMenuBar {{ background: #ffffff; }}
QMenuBar::item:selected, QMenu::item:selected {{ background: #eef2ff; color: {ACCENT_DARK}; }}
QStatusBar {{ background: #ffffff; color: {MUTED}; border-top: 1px solid {BORDER}; }}

QLabel#notes {{ color: #475569; }}
QLabel#warning {{ background: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px;
    padding: 8px 10px; color: #92400e; }}
QLabel#error {{ background: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px;
    padding: 8px 10px; color: #991b1b; }}
"""


def style_sheet() -> str:
    """The style sheet, including a drawn check mark for check boxes."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#ffffff"), 4.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawPolyline(QPolygonF([QPointF(7, 17), QPointF(13.5, 23), QPointF(25, 9)]))
    painter.end()
    path = Path(QDir.tempPath()) / "beamforge_check.png"
    pixmap.save(str(path))
    return (
        STYLE
        + f"""
QCheckBox::indicator, QGroupBox::indicator {{
    width: 16px; height: 16px; border: 1px solid #94a3b8; border-radius: 4px;
    background: #ffffff;
}}
QCheckBox::indicator:checked, QGroupBox::indicator:checked {{
    background: {ACCENT}; border: 1px solid {ACCENT}; image: url("{path.as_posix()}");
}}
"""
    )


def app_icon() -> QIcon:
    """Draw the application icon: a beam converging to a bright focus."""
    pixmap = QPixmap(256, 256)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient = QLinearGradient(0, 0, 256, 256)
    gradient.setColorAt(0.0, QColor(ACCENT_DARK))
    gradient.setColorAt(1.0, QColor(ACCENT))
    painter.setBrush(QBrush(gradient))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(8, 8, 240, 240), 52, 52)
    painter.setBrush(QColor(255, 255, 255, 110))
    painter.drawPolygon(QPolygonF([QPointF(44, 62), QPointF(44, 194), QPointF(186, 128)]))
    painter.setBrush(QColor(255, 255, 255, 70))
    painter.drawEllipse(QPointF(186, 128), 36, 36)
    painter.setBrush(QColor(255, 255, 255))
    painter.drawEllipse(QPointF(186, 128), 17, 17)
    painter.end()
    return QIcon(pixmap)
