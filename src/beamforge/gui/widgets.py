"""Small display pieces shared by the windows: number formatting and result cards."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from beamforge.calculator import Quantity
from beamforge.gui import theme

UNITS = {"um": "µm", "um^2": "µm²", "J/cm^2": "J/cm²", "W/cm^2": "W/cm²"}
PREFIXES = [(1e3, "k"), (1.0, ""), (1e-3, "m"), (1e-6, "µ"), (1e-9, "n")]
SUPERSCRIPT = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def format_number(value: float, digits: int = 4) -> str:
    """Format for display: plain digits in the everyday range, × 10ⁿ outside it."""
    if value == 0:
        return "0"
    size = abs(value)
    if 1e3 <= size < 1e6:
        return f"{value:.0f}"
    if 1e-3 <= size < 1e3:
        return f"{value:.{digits}g}"
    mantissa, exponent = f"{value:.{digits - 1}e}".split("e")
    return f"{mantissa} × 10{str(int(exponent)).translate(SUPERSCRIPT)}"


def display(quantity: Quantity) -> tuple[str, str]:
    """Value text and unit for a result. Joules and watts get an SI prefix."""
    value = quantity.display_value
    unit = UNITS.get(quantity.display_unit, quantity.display_unit)
    if unit in ("J", "W") and value > 0:
        factor, prefix = next((f, p) for f, p in PREFIXES if value >= f or f == 1e-9)
        return format_number(value / factor), prefix + unit
    return format_number(value), unit


class Card(QFrame):
    """One headline number with its definition underneath."""

    def __init__(self, title: str, definition: str) -> None:
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)
        heading = QLabel(title)
        heading.setObjectName("cardTitle")
        self.value = QLabel("—")
        self.value.setObjectName("cardValue")
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        note = QLabel(definition)
        note.setObjectName("cardSub")
        for widget in (heading, self.value, note):
            layout.addWidget(widget)

    def show_quantity(self, quantity: Quantity | None) -> None:
        if quantity is None:
            self.value.setText("—")
        else:
            value, unit = display(quantity)
            self.value.setText(
                f"{value} <span style='font-size:11pt; color:{theme.MUTED}'>{unit}</span>"
            )
