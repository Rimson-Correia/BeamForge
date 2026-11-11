"""Main window: inputs on the left, headline numbers, profile plots and results table."""

from __future__ import annotations

from html import escape
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from beamforge import __version__
from beamforge.beams import E2_LEVEL, GaussianSpot, Spot, sample_profile
from beamforge.calculator import Quantity, Result, Setup, build_spot, calculate
from beamforge.cli import format_report, write_csv
from beamforge.gui import theme
from beamforge.gui.inputs import InputPanel
from beamforge.setup_file import dumps, load_dict, setup_from_dict

REPOSITORY = "https://github.com/Rimson-Correia/BeamForge"

LABELS = {
    "spot_fwhm": "Spot diameter (FWHM)",
    "spot_diameter_1e2": "Spot diameter (1/e²)",
    "a_eff": "Effective area A_eff",
    "waist_radius": "Waist radius w₀",
    "rayleigh_range": "Rayleigh range",
    "first_dark_ring_diameter": "First dark ring diameter",
    "transmission_to_target": "Transmission to target",
    "required_pulse_energy": "Required pulse energy",
    "required_average_power": "Required average power",
    "pulse_energy_on_target": "Pulse energy on target",
    "average_power_on_target": "Average power on target",
    "fluence_peak": "Peak fluence",
    "fluence_average_fwhm_disc": "Average fluence, FWHM disc",
    "fluence_average_1e2_disc": "Average fluence, 1/e² disc",
    "fluence_gaussian_equivalent": "Gaussian-equivalent fluence",
    "intensity_peak": "Peak intensity",
    "pulses_per_spot_fwhm": "Pulses per spot (FWHM diameter)",
    "pulse_overlap_fwhm": "Pulse overlap (FWHM diameter)",
    "pulses_per_spot_1e2": "Pulses per spot (1/e² diameter)",
    "pulse_overlap_1e2": "Pulse overlap (1/e² diameter)",
}
UNITS = {"um": "µm", "um^2": "µm²", "J/cm^2": "J/cm²", "W/cm^2": "W/cm²"}
PREFIXES = [(1e3, "k"), (1.0, ""), (1e-3, "m"), (1e-6, "µ"), (1e-9, "n")]
SUPERSCRIPT = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
CARDS = [
    ("fluence_peak", "PEAK FLUENCE", "F₀ = E / A_eff"),
    ("spot_fwhm", "SPOT DIAMETER", "FWHM of intensity"),
    ("a_eff", "EFFECTIVE AREA", "A_eff = ∬ I / I_max dA"),
    ("intensity_peak", "PEAK INTENSITY", "I₀ = k F₀ / τ"),
]


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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BeamForge")
        self.setWindowIcon(theme.app_icon())
        self.resize(1320, 860)
        self.setup: Setup | None = None
        self.result: Result | None = None
        self.spot: Spot | None = None

        self.inputs = InputPanel()
        scroll = QScrollArea()
        scroll.setWidget(self.inputs)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(440)
        scroll.setMaximumWidth(520)

        right = QWidget()
        column = QVBoxLayout(right)
        column.setContentsMargins(8, 12, 14, 10)
        column.setSpacing(10)

        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()
        column.addWidget(self.error)

        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.cards = {}
        for name, title, definition in CARDS:
            self.cards[name] = Card(title, definition)
            cards.addWidget(self.cards[name])
        column.addLayout(cards)

        self.warning = QLabel()
        self.warning.setObjectName("warning")
        self.warning.setWordWrap(True)
        self.warning.hide()
        column.addWidget(self.warning)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._build_plots())
        splitter.addWidget(self._build_results())
        splitter.setSizes([430, 330])
        splitter.setChildrenCollapsible(False)
        column.addWidget(splitter, 1)

        root = QWidget()
        root.setObjectName("root")
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(scroll)
        row.addWidget(right, 1)
        self.setCentralWidget(root)

        self._build_actions()
        self.statusBar().showMessage(
            f"BeamForge {__version__}   ·   scalar, paraxial, ideal-lens model"
        )

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.recalculate)
        self.inputs.changed.connect(self.timer.start)
        self.recalculate()

    # -- construction ---------------------------------------------------------

    def _build_plots(self) -> QWidget:
        pg.setConfigOptions(antialias=True, foreground="#475569")
        tabs = QTabWidget()

        self.plot = pg.PlotWidget(background="w")
        self.plot.setMenuEnabled(False)
        item = self.plot.getPlotItem()
        item.setLabel("bottom", "Position on target (µm)")
        item.setLabel("left", "Intensity  I / I_max")
        item.showGrid(x=True, y=True, alpha=0.15)
        self.legend = item.addLegend(offset=(-12, 12), labelTextColor="#475569")
        self.reference_shown = True
        self.curve = item.plot(pen=pg.mkPen(theme.ACCENT, width=2.5), name="Selected model")
        self.reference = item.plot(
            pen=pg.mkPen("#94a3b8", width=1.5, style=Qt.PenStyle.DashLine),
            name="Ideal Gaussian, aperture ignored",
        )
        dash = pg.mkPen(theme.AMBER, width=1, style=Qt.PenStyle.DashLine)
        options = {"position": 0.04, "color": "#b45309", "anchors": [(0, 1), (0, 1)]}
        self.half_line = pg.InfiniteLine(angle=0, pen=dash, label="half maximum", labelOpts=options)
        self.e2_line = pg.InfiniteLine(angle=0, pen=dash, label="1/e²", labelOpts=options)
        item.addItem(self.half_line)
        item.addItem(self.e2_line)

        self.log_scale = QCheckBox("Logarithmic intensity axis (shows diffraction rings)")
        self.log_scale.toggled.connect(self._draw_plots)
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(8, 8, 8, 6)
        box.addWidget(self.plot, 1)
        box.addWidget(self.log_scale)
        tabs.addTab(page, "Profile")

        self.map = pg.PlotWidget(background="w")
        self.map.setMenuEnabled(False)
        self.map.setAspectLocked(True)
        self.map.getPlotItem().setLabel("bottom", "x on target (µm)")
        self.map.getPlotItem().setLabel("left", "y on target (µm)")
        self.image = pg.ImageItem()
        self.image.setColorMap(pg.colormap.get("inferno"))
        self.map.addItem(self.image)
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(8, 8, 8, 8)
        box.addWidget(self.map)
        tabs.addTab(page, "Spot on target")
        self.tabs = tabs
        return tabs

    def _build_results(self) -> QWidget:
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Quantity", "Value", "Unit", "Definition"])
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.notes = QLabel()
        self.notes.setObjectName("notes")
        self.notes.setWordWrap(True)
        self.notes.setMinimumHeight(54)
        self.notes.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.notes.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        panel = QWidget()
        box = QVBoxLayout(panel)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        box.addWidget(self.table, 1)
        box.addWidget(self.notes)
        return panel

    def _build_actions(self) -> None:
        def action(text, slot, shortcut=None) -> QAction:
            act = QAction(text, self)
            act.triggered.connect(slot)
            if shortcut is not None:
                act.setShortcut(shortcut)
            return act

        open_ = action("Open setup…", self.open_setup, QKeySequence.StandardKey.Open)
        save = action("Save setup…", self.save_setup, QKeySequence.StandardKey.Save)
        csv = action("Export CSV…", self.export_csv, "Ctrl+E")
        report = action("Export report…", self.export_report, "Ctrl+R")
        copy = action("Copy results", self.copy_results, "Ctrl+Shift+C")
        quit_ = action("Quit", self.close, QKeySequence.StandardKey.Quit)
        about = action("About BeamForge", self.show_about)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addActions([open_, save])
        file_menu.addSeparator()
        file_menu.addActions([csv, report, copy])
        file_menu.addSeparator()
        file_menu.addAction(quit_)
        self.menuBar().addMenu("&Help").addAction(about)

        bar = QToolBar("Main")
        bar.setMovable(False)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        bar.addActions([open_, save])
        bar.addSeparator()
        bar.addActions([csv, report, copy])
        self.addToolBar(bar)

    # -- calculation and display ----------------------------------------------

    def recalculate(self) -> None:
        """Read the inputs, run the library and refresh every view."""
        try:
            setup = setup_from_dict(self.inputs.to_dict())
            result = calculate(setup)
            spot = build_spot(setup)
        except (ValueError, ZeroDivisionError, OverflowError) as error:
            self.error.setText(str(error) or "These inputs cannot be calculated.")
            self.error.show()
            return
        self.error.hide()
        self.setup, self.result, self.spot = setup, result, spot
        self._show_result()
        self._draw_plots()

    def _show_result(self) -> None:
        result = self.result
        by_name = {q.name: q for q in result.quantities}
        for name, card in self.cards.items():
            card.show_quantity(by_name.get(name))

        self.table.setRowCount(len(result.quantities))
        for row, quantity in enumerate(result.quantities):
            value, unit = display(quantity)
            cells = [LABELS.get(quantity.name, quantity.name), value, unit, quantity.definition]
            for column, text in enumerate(cells):
                cell = QTableWidgetItem(text)
                if column == 1:
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, column, cell)

        if result.warnings:
            self.warning.setText("<br>".join(f"⚠  {escape(w)}" for w in result.warnings))
        self.warning.setVisible(bool(result.warnings))
        assumptions = escape("; ".join(result.assumptions))
        self.notes.setText(
            f"<b>Model:</b> {escape(result.model)}. <b>Assumptions:</b> {assumptions}."
        )

    def _draw_plots(self) -> None:
        if self.spot is None:
            return
        radii, values = sample_profile(self.spot, points=300)
        micron = radii * 1e6
        log = self.log_scale.isChecked()

        def both_sides(v: np.ndarray) -> np.ndarray:
            return np.concatenate([v[:0:-1], v])

        def scaled(v: np.ndarray) -> np.ndarray:
            return np.log10(np.clip(v, 1e-6, None)) if log else v

        x = np.concatenate([-micron[:0:-1], micron])
        self.curve.setData(x, scaled(both_sides(values)))
        self.curve.setFillLevel(None if log else 0.0)
        self.curve.setBrush(None if log else pg.mkBrush(37, 99, 235, 36))

        setup = self.setup
        compare = setup.model == "truncated_gaussian"
        if compare:
            ideal = GaussianSpot(setup.wavelength, setup.focal_length, setup.beam_radius)
            self.reference.setData(x, scaled(both_sides(np.asarray(ideal.profile(radii)))))
        else:
            self.reference.setData([], [])
        if compare != self.reference_shown:
            if compare:
                self.legend.addItem(self.reference, "Ideal Gaussian, aperture ignored")
            else:
                self.legend.removeItem(self.reference)
            self.reference_shown = compare
        self.half_line.setValue(float(scaled(np.array(0.5))))
        self.e2_line.setValue(float(scaled(np.array(E2_LEVEL))))

        item = self.plot.getPlotItem()
        item.setLabel("left", "log₁₀ ( I / I_max )" if log else "Intensity  I / I_max")
        item.setXRange(x[0], x[-1], padding=0.02)
        item.setYRange(-6.0 if log else 0.0, 0.0 if log else 1.05, padding=0.02)

        edge = micron[-1]
        axis = np.linspace(-edge, edge, 301)
        distance = np.hypot(*np.meshgrid(axis, axis))
        self.image.setImage(np.interp(distance, micron, values, right=0.0), levels=(0.0, 1.0))
        self.image.setRect(QRectF(-edge, -edge, 2 * edge, 2 * edge))
        self.map.getPlotItem().setRange(xRange=(-edge, edge), yRange=(-edge, edge), padding=0.02)

    # -- file actions ---------------------------------------------------------

    def _fail(self, title: str, error: Exception) -> None:
        QMessageBox.warning(self, title, str(error))

    def open_setup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open setup", "", "Setup files (*.toml)")
        if path:
            self.load_file(path)

    def load_file(self, path: str | Path) -> None:
        try:
            data = load_dict(path)
            setup_from_dict(data)  # reject unknown keys before touching the inputs
        except (OSError, ValueError) as error:
            self._fail("Could not open setup", error)
            return
        self.inputs.from_dict(data)
        self.recalculate()
        self.setWindowTitle(f"BeamForge — {Path(path).name}")

    def save_setup(self) -> None:
        try:
            text = dumps(self.inputs.to_dict())
        except ValueError as error:
            self._fail("Cannot save setup", error)
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save setup", "setup.toml", "Setup files (*.toml)"
        )
        if path:
            try:
                Path(path).write_text(text, encoding="utf-8")
            except OSError as error:
                self._fail("Cannot save setup", error)

    def export_csv(self) -> None:
        if self.result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export results", "results.csv", "CSV files (*.csv)"
        )
        if path:
            try:
                write_csv(path, self.result)
            except OSError as error:
                self._fail("Cannot export", error)

    def export_report(self) -> None:
        if self.result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export report", "report.txt", "Text files (*.txt)"
        )
        if path:
            try:
                Path(path).write_text(
                    format_report(self.setup, self.result) + "\n", encoding="utf-8"
                )
            except OSError as error:
                self._fail("Cannot export", error)

    def copy_results(self) -> None:
        rows = [
            "\t".join(self.table.item(r, c).text() for c in range(self.table.columnCount()))
            for r in range(self.table.rowCount())
        ]
        QGuiApplication.clipboard().setText("\n".join(rows))
        self.statusBar().showMessage("Results copied to the clipboard", 3000)

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About BeamForge",
            f"<h3>BeamForge {__version__}</h3>"
            "<p>Laser parameters on target, with the fluence computed from the "
            "actual focal profile of the chosen beam model.</p>"
            "<p>Models are scalar and paraxial and assume an ideal lens. Every "
            "result is shown with its definition.</p>"
            f"<p>MIT licence · <a href='{REPOSITORY}'>{REPOSITORY}</a></p>",
        )
