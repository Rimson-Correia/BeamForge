"""The input panel: collects the setup in the same structure as a setup file.

``InputPanel.to_dict()`` returns exactly what a TOML setup file contains, so the
GUI, the file format and the command line share one input boundary
(:func:`beamforge.setup_file.setup_from_dict`).
"""

from __future__ import annotations

import math
import re
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

MODELS = [
    ("truncated_gaussian", "Truncated Gaussian"),
    ("gaussian", "Gaussian (ideal or M²)"),
    ("airy", "Uniform aperture (Airy)"),
    ("flat_top", "Flat-top at target"),
]
ENERGY_MODES = [
    ("average_power_w", "Average power", "W"),
    ("pulse_energy_uj", "Pulse energy", "µJ"),
    ("target_peak_fluence_j_cm2", "Target peak fluence", "J/cm²"),
    ("", "Optics only (no energy)", ""),
]
Key = tuple[str, str]
LABEL_WIDTH = 150


def _text(value: float) -> str:
    return f"{value:.10g}"


class NumberEdit(QLineEdit):
    """A text field for one number. Accepts plain and scientific notation (1.5e-3)."""

    def __init__(self, text: str = "", optional: bool = False, positive: bool = True) -> None:
        super().__init__(text)
        self.optional = optional
        self.positive = positive
        self.textChanged.connect(self.restyle)

    def value(self) -> float | None:
        """The number, or ``None`` if the field is empty or not a valid number."""
        try:
            number = float(self.text().strip().replace(",", "."))
        except ValueError:
            return None
        if not math.isfinite(number) or (self.positive and number <= 0):
            return None
        return number

    def is_valid(self) -> bool:
        return self.value() is not None or (self.optional and not self.text().strip())

    def restyle(self) -> None:
        self.setProperty("invalid", not self.is_valid())
        self.style().unpolish(self)
        self.style().polish(self)


class InputPanel(QWidget):
    """All user inputs, grouped as in SPEC.md section 2."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("inputs")
        self.numbers: dict[Key, NumberEdit] = {}
        self.combos: dict[Key, QComboBox] = {}
        self.rows: dict[Key, tuple[QFormLayout, QWidget]] = {}
        self.labels: dict[Key, str] = {}
        self.shown: dict[Key, bool] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 4, 8, 12)
        layout.setSpacing(4)

        form = self._group(layout, "Laser")
        self._number(form, "laser", "wavelength_nm", "Wavelength", "nm", "800")
        self._number(form, "laser", "rep_rate_hz", "Repetition rate", "Hz", "1000", optional=True)
        self._number(
            form, "laser", "pulse_duration_fs", "Pulse duration (FWHM)", "fs", "100", optional=True
        )
        self._combo(
            form,
            "laser",
            "pulse_shape",
            "Pulse shape",
            [("gaussian", "Gaussian"), ("sech2", "sech²"), ("rectangular", "Rectangular")],
        )

        form = self._group(layout, "Beam model")
        self._combo(form, "beam", "model", "Model", MODELS)
        self._number(form, "beam", "diameter_mm", "Beam diameter at lens", "mm", "10")
        self._combo(
            form,
            "beam",
            "diameter_definition",
            "Diameter definition",
            [("1/e2", "1/e² diameter"), ("fwhm", "FWHM diameter")],
        )
        self._number(form, "beam", "m2", "Beam quality M²", "", "1")
        self._number(form, "beam", "flat_top_diameter_um", "Spot diameter on target", "µm", "100")

        self.aperture_box = QGroupBox("Aperture")
        layout.addWidget(self.aperture_box)
        form = QFormLayout(self.aperture_box)
        self._number(form, "aperture", "diameter_mm", "Aperture diameter", "mm", "5")
        self.aperture_box.toggled.connect(self._on_change)

        self.focus_box = QGroupBox("Focusing")
        layout.addWidget(self.focus_box)
        form = QFormLayout(self.focus_box)
        self._number(form, "focusing", "focal_length_mm", "Focal length", "mm", "350")
        self._number(
            form, "focusing", "defocus_mm", "Target distance from focus", "mm", "0", positive=False
        )

        form = self._group(layout, "Energy")
        self.energy_form = form
        self.energy_mode = QComboBox()
        self.energy_mode.setItemDelegate(QStyledItemDelegate(self.energy_mode))
        for key, label, _unit in ENERGY_MODES:
            self.energy_mode.addItem(label, key)
        self.energy_mode.currentIndexChanged.connect(self._on_change)
        self.energy_mode.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.energy_mode.setMinimumContentsLength(12)
        self._add_row(form, "Known quantity", self._with_unit(self.energy_mode, QLabel("")))
        self.energy_value = NumberEdit("1")
        self.energy_value.textChanged.connect(self.changed)
        self.energy_unit = QLabel("W")
        self.energy_row = self._with_unit(self.energy_value, self.energy_unit)
        self._add_row(form, "Value", self.energy_row)
        self._combo(
            form,
            "energy",
            "measured",
            "Measured",
            [("before_aperture", "Before the aperture"), ("after_aperture", "After the aperture")],
        )
        self.transmissions = QLineEdit("")
        self.transmissions.setPlaceholderText("e.g. 0.95, 0.99  (empty = no losses)")
        self.transmissions.textChanged.connect(self.changed)
        self.transmission_row = self._with_unit(self.transmissions, QLabel(""))
        self._add_row(form, "Transmissions to target", self.transmission_row)

        for form in self.findChildren(QFormLayout):
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addStretch(1)
        self._update_visibility()

    # -- construction helpers -------------------------------------------------

    def _group(self, layout: QVBoxLayout, title: str) -> QFormLayout:
        box = QGroupBox(title)
        layout.addWidget(box)
        return QFormLayout(box)

    @staticmethod
    def _with_unit(edit: QWidget, unit: QLabel) -> QWidget:
        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(edit, 1)
        unit.setProperty("role", "unit")
        unit.setFixedWidth(44)
        box.addWidget(unit)
        return row

    @staticmethod
    def _add_row(form: QFormLayout, label: str, row: QWidget) -> None:
        """Add a row with a fixed label width, so fields line up across groups."""
        form.addRow(label, row)
        form.labelForField(row).setMinimumWidth(LABEL_WIDTH)

    def _number(
        self, form, section, key, label, unit, default="", optional=False, positive=True
    ) -> None:
        edit = NumberEdit(default, optional, positive)
        edit.textChanged.connect(self.changed)
        row = self._with_unit(edit, QLabel(unit))
        self._add_row(form, label, row)
        self.numbers[(section, key)] = edit
        self.rows[(section, key)] = (form, row)
        self.labels[(section, key)] = label

    def _combo(self, form, section, key, label, options) -> None:
        combo = QComboBox()
        # A styled delegate makes the drop-down list follow the style sheet.
        combo.setItemDelegate(QStyledItemDelegate(combo))
        for value, text in options:
            combo.addItem(text, value)
        combo.currentIndexChanged.connect(self._on_change)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(12)
        row = self._with_unit(combo, QLabel(""))
        self._add_row(form, label, row)
        self.combos[(section, key)] = combo
        self.rows[(section, key)] = (form, row)
        self.labels[(section, key)] = label

    # -- behaviour ------------------------------------------------------------

    def _on_change(self, *_args) -> None:
        self._update_visibility()
        self.changed.emit()

    def _update_visibility(self) -> None:
        """Show only the inputs the selected model and energy mode use."""
        model = self.combos[("beam", "model")].currentData()
        mode = self.energy_mode.currentData()
        focused = model != "flat_top"
        self.shown = {
            ("beam", "diameter_mm"): focused,
            ("beam", "diameter_definition"): focused,
            ("beam", "m2"): model == "gaussian",
            ("beam", "flat_top_diameter_um"): model == "flat_top",
            ("focusing", "defocus_mm"): model == "gaussian",
            ("energy", "measured"): model == "truncated_gaussian" and bool(mode),
        }
        for key, visible in self.shown.items():
            form, row = self.rows[key]
            form.setRowVisible(row, visible)
        # The Airy model does not need the beam diameter; it is only used for a warning.
        diameter = self.numbers[("beam", "diameter_mm")]
        diameter.optional = model == "airy"
        diameter.setPlaceholderText("optional" if model == "airy" else "")
        diameter.restyle()

        self.focus_box.setVisible(focused)
        self.aperture_box.setVisible(focused)
        # The aperture is optional for the Gaussian model, required for the others.
        # (setCheckable re-checks the box, so only call it when the state changes.)
        if self.aperture_box.isCheckable() != (model == "gaussian"):
            was_blocked = self.aperture_box.blockSignals(True)
            self.aperture_box.setCheckable(model == "gaussian")
            self.aperture_box.blockSignals(was_blocked)

        self.energy_form.setRowVisible(self.energy_row, bool(mode))
        self.energy_form.setRowVisible(self.transmission_row, bool(mode))
        self.energy_unit.setText(ENERGY_MODES[self.energy_mode.currentIndex()][2])

    def _use_aperture(self) -> bool:
        return not self.aperture_box.isCheckable() or self.aperture_box.isChecked()

    def _read(self, key: Key) -> float | None:
        edit = self.numbers[key]
        value = edit.value()
        if value is None and not (edit.optional and not edit.text().strip()):
            raise ValueError(f"Enter a valid number for “{self.labels[key]}”.")
        return value

    def to_dict(self) -> dict[str, Any]:
        """The current inputs in setup-file structure. Raises ValueError if invalid."""
        data: dict[str, dict[str, Any]] = {
            name: {} for name in ("laser", "energy", "beam", "aperture", "focusing")
        }
        model = self.combos[("beam", "model")].currentData()
        mode = self.energy_mode.currentData()

        def put(section: str, key: str) -> None:
            if self.shown.get((section, key), True):
                value = self._read((section, key))
                if value is not None:
                    data[section][key] = value

        put("laser", "wavelength_nm")
        put("laser", "rep_rate_hz")
        put("laser", "pulse_duration_fs")
        data["laser"]["pulse_shape"] = self.combos[("laser", "pulse_shape")].currentData()

        data["beam"]["model"] = model
        put("beam", "diameter_mm")
        if "diameter_mm" in data["beam"]:
            data["beam"]["diameter_definition"] = self.combos[
                ("beam", "diameter_definition")
            ].currentData()
        put("beam", "m2")
        put("beam", "flat_top_diameter_um")
        if model != "flat_top":
            if self._use_aperture():
                put("aperture", "diameter_mm")
            put("focusing", "focal_length_mm")
            put("focusing", "defocus_mm")

        if mode:
            value = self.energy_value.value()
            if value is None:
                raise ValueError("Enter a valid number for the energy value.")
            if mode == "average_power_w" and "rep_rate_hz" not in data["laser"]:
                raise ValueError(
                    "The repetition rate is needed to convert average power to pulse energy."
                )
            data["energy"][mode] = value
            if self.shown[("energy", "measured")]:
                data["energy"]["measured"] = self.combos[("energy", "measured")].currentData()
            parts = [p for p in re.split(r"[,;\s]+", self.transmissions.text().strip()) if p]
            try:
                transmissions = [float(p) for p in parts]
            except ValueError:
                raise ValueError(
                    "Transmissions must be numbers between 0 and 1, separated by commas."
                ) from None
            if transmissions:
                data["energy"]["transmissions"] = transmissions

        return {section: content for section, content in data.items() if content}

    def from_dict(self, data: dict[str, Any]) -> None:
        """Fill the panel from setup-file structure (the inverse of ``to_dict``)."""
        self.blockSignals(True)
        try:
            for (section, key), combo in self.combos.items():
                value = data.get(section, {}).get(key)
                index = combo.findData(value)
                if index >= 0:
                    combo.setCurrentIndex(index)
            defaults = {("beam", "m2"): "1", ("focusing", "defocus_mm"): "0"}
            for (section, key), edit in self.numbers.items():
                value = data.get(section, {}).get(key)
                if value is not None:
                    edit.setText(_text(float(value)))
                elif (section, key) in defaults:
                    edit.setText(defaults[(section, key)])
                elif edit.optional:
                    edit.setText("")

            energy = dict(data.get("energy", {}))
            if "pulse_energy_j" in energy:
                energy["pulse_energy_uj"] = float(energy.pop("pulse_energy_j")) * 1e6
            mode_index = len(ENERGY_MODES) - 1
            for index, (key, _label, _unit) in enumerate(ENERGY_MODES):
                if key and key in energy:
                    mode_index = index
                    self.energy_value.setText(_text(float(energy[key])))
            self.energy_mode.setCurrentIndex(mode_index)
            self.transmissions.setText(
                ", ".join(_text(float(t)) for t in energy.get("transmissions", []))
            )
            self._update_visibility()
            if self.aperture_box.isCheckable():
                self.aperture_box.setChecked("diameter_mm" in data.get("aperture", {}))
        finally:
            self.blockSignals(False)
        self._update_visibility()
        self.changed.emit()
