"""Desktop interface: runs without a display. Skipped if the GUI extras are missing."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6.QtWidgets import QApplication  # noqa: E402

from beamforge.calculator import Setup, calculate  # noqa: E402
from beamforge.gui import splash  # noqa: E402
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


def example_without_scanning():
    """The example setup as the window sees it: the window has no scanning inputs."""
    data = load_dict(EXAMPLE)
    data.pop("scanning", None)
    return data


def test_window_shows_library_results(window):
    window.load_file(EXAMPLE)
    expected = calculate(setup_from_dict(example_without_scanning()))
    assert window.result["fluence_peak"].value == pytest.approx(expected["fluence_peak"].value)
    assert window.table.rowCount() == len(expected.quantities)
    assert "58.94" in window.cards["spot_fwhm"].value.text()
    assert "scalar" in window.notes.text()
    assert window.error.isHidden()


def test_inputs_round_trip_through_setup_file(window, tmp_path):
    window.load_file(EXAMPLE)
    saved = tmp_path / "saved.toml"
    saved.write_text(dumps(window.inputs.to_dict()), encoding="utf-8")
    assert setup_from_dict(load_dict(saved)) == setup_from_dict(example_without_scanning())


def test_new_window_uses_library_defaults(window):
    library = Setup(model="truncated_gaussian")
    assert window.setup.measured == library.measured
    assert window.setup.pulse_shape == library.pulse_shape


def test_loading_a_file_resets_settings_it_leaves_out(window, tmp_path):
    sparse = {
        "laser": {"wavelength_nm": 800, "rep_rate_hz": 2000, "pulse_duration_fs": 100},
        "energy": {"pulse_energy_uj": 40},
        "beam": {"model": "truncated_gaussian", "diameter_mm": 10},
        "aperture": {"diameter_mm": 5},
        "focusing": {"focal_length_mm": 350},
    }
    full = {section: dict(content) for section, content in sparse.items()}
    full["laser"]["pulse_shape"] = "sech2"
    full["energy"].update(measured="before_aperture", transmissions=[0.5])
    full["beam"]["diameter_definition"] = "fwhm"
    for name, data in (("full.toml", full), ("sparse.toml", sparse)):
        (tmp_path / name).write_text(dumps(data), encoding="utf-8")
    window.load_file(tmp_path / "full.toml")
    window.load_file(tmp_path / "sparse.toml")
    assert window.setup == setup_from_dict(sparse)
    expected = calculate(setup_from_dict(sparse))
    assert window.result["fluence_peak"].value == pytest.approx(expected["fluence_peak"].value)


def test_file_the_library_cannot_calculate_is_refused(window, tmp_path, monkeypatch):
    window.load_file(EXAMPLE)
    before = window.setup
    data = example_without_scanning()
    data.pop("aperture")
    path = tmp_path / "incomplete.toml"
    path.write_text(dumps(data), encoding="utf-8")
    messages = []
    monkeypatch.setattr(window, "_fail", lambda title, error: messages.append(str(error)))
    window.load_file(path)
    assert messages and "aperture" in messages[0]
    assert window.setup == before


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


def test_splash_draws_still_and_animated(app):
    still = splash.still_image()
    assert (still.width(), still.height()) == (splash.WIDTH, splash.HEIGHT)
    widget = splash.Splash()
    frame = widget.grab().toImage()
    widget.close()
    assert frame.width() == splash.WIDTH
    # the loading bar is the only difference between the two pictures
    row = int(splash.TRACK.center().y())
    assert any(
        frame.pixel(x, row) != still.pixel(x, row)
        for x in range(int(splash.TRACK.left()), int(splash.TRACK.right()))
    )
