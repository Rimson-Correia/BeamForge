"""The Depth of focus window: Rayleigh length and spot size away from best focus.

It shows what :func:`beamforge.calculator.through_focus` returns. No physics here.
"""

from __future__ import annotations

from html import escape

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from beamforge.calculator import FocusScan, Quantity, Result, Setup, through_focus
from beamforge.cli import write_focus_csv
from beamforge.gui import theme
from beamforge.gui.widgets import Card, format_number

GREEN = "#059669"


def _length(name: str, value: float, definition: str) -> Quantity:
    return Quantity(name, value, "m", 1e3, "mm", definition)


class FocusWindow(QDialog):
    """A separate window that follows the main window's inputs while it is open."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Depth of focus — BeamForge")
        self.setWindowIcon(theme.app_icon())
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.resize(1180, 820)
        self.setObjectName("root")
        self.scan: FocusScan | None = None
        self.energy: float | None = None

        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(10)

        lead = QLabel(
            "Spot size and peak fluence when the target moves away from best focus. "
            "Negative distances are toward the lens, positive away from it. "
            "The Rayleigh length is where the peak fluence has fallen to half. Far from "
            "focus the spot breaks into rings: the FWHM and 1/e² diameters then jump when "
            "a ring crosses their level, and in the grey region the centre is no longer the "
            "brightest point. The peak fluence stays well defined everywhere."
        )
        lead.setWordWrap(True)
        lead.setObjectName("notes")
        column.addWidget(lead)

        self.message = QLabel()
        self.message.setObjectName("warning")
        self.message.setWordWrap(True)
        self.message.hide()
        column.addWidget(self.message)

        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.cards = {
            "toward": Card("RAYLEIGH LENGTH, TOWARD LENS", "peak fluence falls to half"),
            "away": Card("RAYLEIGH LENGTH, AWAY FROM LENS", "peak fluence falls to half"),
            "depth": Card("DEPTH OF FOCUS", "between the two half-fluence points"),
            "offset": Card("BEST FOCUS", "from the focal plane (lens + f)"),
        }
        for card in self.cards.values():
            cards.addWidget(card)
        column.addLayout(cards)

        plots = QWidget()
        row = QHBoxLayout(plots)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.size_plot = self._plot("Spot diameter (µm)")
        self.fluence_plot = self._plot("Peak fluence")
        row.addWidget(self.size_plot)
        row.addWidget(self.fluence_plot)
        size_item = self.size_plot.getPlotItem()
        legend = size_item.addLegend(labelTextColor="#475569")
        legend.anchor(itemPos=(0.5, 0.0), parentPos=(0.5, 0.0), offset=(0, 8))
        self.fwhm_curve = size_item.plot(pen=pg.mkPen(theme.ACCENT, width=2.5), name="FWHM")
        self.e2_curve = size_item.plot(pen=pg.mkPen(theme.ACCENT_DARK, width=2.5), name="1/e²")
        self.fluence_curve = self.fluence_plot.getPlotItem().plot(
            pen=pg.mkPen(theme.ACCENT, width=2.5), fillLevel=0.0, brush=pg.mkBrush(37, 99, 235, 36)
        )
        self.half_line = pg.InfiniteLine(
            angle=0,
            pen=pg.mkPen(theme.AMBER, width=1, style=Qt.PenStyle.DashLine),
            label="half of best",
            labelOpts={"position": 0.05, "color": "#b45309", "anchors": [(0, 1), (0, 1)]},
        )
        self.fluence_plot.addItem(self.half_line)
        self.markers: list[tuple[pg.PlotWidget, pg.GraphicsObject]] = []

        self.table = QTableWidget(0, 6)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(plots)
        splitter.addWidget(self.table)
        splitter.setSizes([440, 260])
        splitter.setChildrenCollapsible(False)
        column.addWidget(splitter, 1)

        self.notes = QLabel()
        self.notes.setObjectName("notes")
        self.notes.setWordWrap(True)
        self.notes.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        column.addWidget(self.notes)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.export_button = QPushButton("Export CSV…")
        self.export_button.clicked.connect(self.export_csv)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        buttons.addWidget(self.export_button)
        buttons.addWidget(close)
        column.addLayout(buttons)

    def _plot(self, ylabel: str) -> pg.PlotWidget:
        plot = pg.PlotWidget(background="w")
        plot.setMenuEnabled(False)
        item = plot.getPlotItem()
        item.setLabel("bottom", "Target distance from best focus (mm)   ← toward the lens · away →")
        item.setLabel("left", ylabel)
        item.showGrid(x=True, y=True, alpha=0.15)
        return plot

    # -- update ---------------------------------------------------------------

    def refresh(self, setup: Setup, result: Result) -> None:
        """Recompute the through-focus table for the main window's current setup."""
        if setup.model == "flat_top":
            self._unavailable(
                "The flat-top model describes a spot of given size on the target and has no "
                "propagation, so it has no depth of focus. Choose another beam model."
            )
            return
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            scan = through_focus(setup)
        except (ValueError, RuntimeError) as error:
            self._unavailable(str(error))
            return
        finally:
            QGuiApplication.restoreOverrideCursor()
        values = {q.name: q.value for q in result.quantities}
        self.scan, self.energy = scan, values.get("pulse_energy_on_target")
        self.message.setVisible(bool(result.warnings))
        self.message.setText("<br>".join(f"⚠  {escape(w)}" for w in result.warnings))
        self._show_cards(scan)
        self._draw(scan, setup.defocus)
        self._fill_table(scan)
        self.export_button.setEnabled(True)
        self.notes.setText(
            f"<b>Model:</b> {escape(result.model)}. <b>Assumptions:</b> "
            f"{escape('; '.join(result.assumptions))}."
        )

    def _unavailable(self, text: str) -> None:
        self.scan = None
        self.message.setText(escape(text))
        self.message.show()
        for card in self.cards.values():
            card.show_quantity(None)
        self.fwhm_curve.setData([], [])
        self.e2_curve.setData([], [])
        self.fluence_curve.setData([], [])
        self._clear_markers()
        self.table.setRowCount(0)
        self.export_button.setEnabled(False)
        self.notes.setText("")

    def _show_cards(self, scan: FocusScan) -> None:
        toward, away = scan.rayleigh_toward_lens, scan.rayleigh_away_from_lens
        self.cards["toward"].show_quantity(_length("toward", toward, ""))
        self.cards["away"].show_quantity(_length("away", away, ""))
        self.cards["depth"].show_quantity(_length("depth", toward + away, ""))
        self.cards["offset"].show_quantity(_length("offset", scan.best_focus_offset, ""))

    def _clear_markers(self) -> None:
        for plot, line in self.markers:
            plot.removeItem(line)
        self.markers = []

    def _draw(self, scan: FocusScan, target: float) -> None:
        mm = scan.distance * 1e3
        self.fwhm_curve.setData(mm, scan.fwhm * 1e6)
        self.e2_curve.setData(mm, scan.diameter_1e2 * 1e6)
        if self.energy is not None:
            fluence = self.energy / scan.a_eff * 1e-4
            self.fluence_plot.getPlotItem().setLabel("left", "Peak fluence (J/cm²)")
        else:
            fluence = scan.relative_peak_fluence
            self.fluence_plot.getPlotItem().setLabel("left", "Peak fluence / best focus")
        self.fluence_curve.setData(mm, fluence)
        self.half_line.setValue(float(np.max(fluence)) / 2.0)
        self.fluence_plot.getPlotItem().setYRange(0.0, float(np.max(fluence)) * 1.08, padding=0)

        self._clear_markers()
        rayleigh = pg.mkPen(theme.AMBER, width=1.5, style=Qt.PenStyle.DashLine)
        target_pen = pg.mkPen(GREEN, width=2)
        options = {"position": 0.92, "color": "#475569", "anchors": [(0.5, 1), (0.5, 1)]}
        ring = ~scan.centre_is_peak
        edges = np.flatnonzero(np.diff(np.concatenate([[0], ring.astype(int), [0]])))
        for plot in (self.size_plot, self.fluence_plot):
            for start, stop in zip(edges[::2], edges[1::2], strict=True):
                region = pg.LinearRegionItem(
                    values=(mm[max(start - 1, 0)], mm[min(stop, len(mm) - 1)]),
                    movable=False,
                    brush=pg.mkBrush(148, 163, 184, 45),
                    pen=pg.mkPen(None),
                )
                plot.addItem(region)
                self.markers.append((plot, region))
            for x, label, pen in (
                (-scan.rayleigh_toward_lens * 1e3, "−Rayleigh", rayleigh),
                (scan.rayleigh_away_from_lens * 1e3, "+Rayleigh", rayleigh),
                (target * 1e3, "target", target_pen),
            ):
                line = pg.InfiniteLine(pos=x, angle=90, pen=pen, label=label, labelOpts=options)
                plot.addItem(line)
                self.markers.append((plot, line))
            plot.getPlotItem().setXRange(mm[0], mm[-1], padding=0.02)

    def _fill_table(self, scan: FocusScan) -> None:
        fluence_header = (
            "Peak fluence (J/cm²)" if self.energy is not None else "Peak fluence / best"
        )
        self.table.setHorizontalHeaderLabels(
            [
                "Distance from best focus (mm)",
                "FWHM (µm)",
                "1/e² diameter (µm)",
                "A_eff (µm²)",
                fluence_header,
                "Spot shape",
            ]
        )
        self.table.setRowCount(len(scan.distance))
        for row in range(len(scan.distance)):
            fluence = (
                self.energy / scan.a_eff[row] * 1e-4
                if self.energy is not None
                else scan.relative_peak_fluence[row]
            )
            cells = [
                f"{scan.distance[row] * 1e3:+.3f}",
                format_number(scan.fwhm[row] * 1e6),
                format_number(scan.diameter_1e2[row] * 1e6),
                format_number(scan.a_eff[row] * 1e12),
                format_number(fluence),
                "centre brightest" if scan.centre_is_peak[row] else "ring-shaped",
            ]
            for column, text in enumerate(cells):
                cell = QTableWidgetItem(text)
                cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, cell)

    # -- export ---------------------------------------------------------------

    def export_csv(self) -> None:
        if self.scan is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export through-focus table", "through_focus.csv", "CSV files (*.csv)"
        )
        if path:
            try:
                write_focus_csv(path, self.scan, self.energy)
            except OSError as error:
                QMessageBox.warning(self, "Cannot export", str(error))
