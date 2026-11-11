"""Desktop interface: runs without a display. Skipped if the GUI extras are missing."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6.QtWidgets import QApplication  # noqa: E402

from beamforge.calculator import calculate  # noqa: E402
from beamforge.gui.main_window import MainWindow, format_number  # noqa: E402
from beamforge.setup_file import dumps, load_dict, setup_from_dict  # noqa: E402

EXAMPLE = Path(__file__).parent.parent / "examples" / "reference_setup.toml"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    win = MainWindow()
    yield win
    win.close()


def select(window, value):
    combo = window.inputs.combos[("beam", "model")]
    combo.setCurrentIndex(combo.findData(value))
    window.recalculate()


def test_window_shows_library_results(window):
    window.load_file(EXAMPLE)
    expected = calculate(setup_from_dict(load_dict(EXAMPLE)))
    assert window.result["fluence_peak"].value == pytest.approx(expected["fluence_peak"].value)
    assert window.table.rowCount() == len(expected.quantities)
    assert "58.94" in window.cards["spot_fwhm"].value.text()
    assert "scalar" in window.notes.text()
    assert window.error.isHidden()


def test_inputs_round_trip_through_setup_file(window, tmp_path):
    window.load_file(EXAMPLE)
    saved = tmp_path / "saved.toml"
    saved.write_text(dumps(window.inputs.to_dict()), encoding="utf-8")
    assert setup_from_dict(load_dict(saved)) == setup_from_dict(load_dict(EXAMPLE))


def test_every_model_calculates(window):
    window.load_file(EXAMPLE)
    for model in ("gaussian", "airy", "flat_top", "truncated_gaussian"):
        select(window, model)
        assert window.error.isHidden(), window.error.text()
        assert window.setup.model == model
        assert window.result["a_eff"].value > 0


def test_gaussian_with_clipping_aperture_warns(window):
    window.load_file(EXAMPLE)
    select(window, "gaussian")
    assert not window.warning.isHidden()
    assert "clips" in window.warning.text()
    window.inputs.aperture_box.setChecked(False)
    window.recalculate()
    assert window.warning.isHidden()


def test_invalid_input_shows_message_and_keeps_last_result(window):
    window.load_file(EXAMPLE)
    before = window.result
    window.inputs.numbers[("laser", "wavelength_nm")].setText("abc")
    window.recalculate()
    assert not window.error.isHidden()
    assert "Wavelength" in window.error.text()
    assert window.result is before


def test_reverse_direction(window):
    window.load_file(EXAMPLE)
    mode = window.inputs.energy_mode
    mode.setCurrentIndex(mode.findData("target_peak_fluence_j_cm2"))
    window.inputs.energy_value.setText("2")
    window.recalculate()
    assert window.result["fluence_peak"].display_value == pytest.approx(2.0)
    assert window.result["required_average_power"].value > 0


def test_format_number():
    assert format_number(58.937) == "58.94"
    assert format_number(4013.7) == "4014"
    assert format_number(58937.0) == "58937"
    assert format_number(8.7491e13) == "8.749 × 10¹³"
    assert format_number(3.5e-7) == "3.500 × 10⁻⁷"
    assert format_number(0.0) == "0"
