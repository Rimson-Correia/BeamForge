"""End-to-end: Setup -> results, setup file, CLI."""

from pathlib import Path

import pytest

from beamforge.calculator import Setup, calculate
from beamforge.cli import main
from beamforge.setup_file import load_setup, setup_from_dict

EXAMPLE = Path(__file__).parent.parent / "examples" / "reference_setup.toml"
OPTICS = dict(wavelength=800e-9, focal_length=0.35, beam_radius=5e-3, aperture_radius=2.5e-3)


def test_forward_truncated_gaussian():
    setup = Setup(
        model="truncated_gaussian",
        **OPTICS,
        rep_rate=1000.0,
        average_power=1.0,
        measured="before_aperture",
        transmissions=(0.5,),
        pulse_duration=100e-15,
        scan_speed=0.01,
    )
    result = calculate(setup)
    trans = 0.5 * 0.393469
    assert result["transmission_to_target"].value == pytest.approx(trans, rel=1e-5)
    energy = 1e-3 * trans
    assert result["pulse_energy_on_target"].value == pytest.approx(energy, rel=1e-5)
    a_eff = result["a_eff"].value
    assert result["fluence_peak"].value == pytest.approx(energy / a_eff)
    assert result["fluence_peak"].display_unit == "J/cm^2"
    assert result["fluence_peak"].display_value == pytest.approx(energy / a_eff * 1e-4)
    assert result["intensity_peak"].value == pytest.approx(
        0.9394 * energy / a_eff / 100e-15, rel=1e-4
    )
    assert result["pulses_per_spot_fwhm"].value == pytest.approx(
        result["spot_fwhm"].value * 1000.0 / 0.01
    )
    assert not result.warnings


def test_reverse_direction_round_trip():
    forward = calculate(Setup(model="airy", **OPTICS, rep_rate=1000.0, average_power=0.2))
    target = forward["fluence_peak"].value
    reverse = calculate(Setup(model="airy", **OPTICS, rep_rate=1000.0, target_peak_fluence=target))
    assert reverse["required_average_power"].value == pytest.approx(0.2)
    assert reverse["required_pulse_energy"].value == pytest.approx(0.2e-3)


def test_optics_only_and_warnings():
    result = calculate(Setup(model="gaussian", **OPTICS))
    assert result["waist_radius"].value == pytest.approx(17.825e-6, rel=1e-4)
    assert any("clips" in w for w in result.warnings)
    with pytest.raises(KeyError):
        result["fluence_peak"]


def test_invalid_setups():
    with pytest.raises(ValueError, match="needs"):
        calculate(Setup(model="airy", wavelength=800e-9))
    with pytest.raises(ValueError, match="defocus"):
        calculate(Setup(model="airy", **OPTICS, defocus=1e-3))
    with pytest.raises(ValueError, match="only one"):
        calculate(Setup(model="airy", **OPTICS, pulse_energy=1.0, target_peak_fluence=1.0))
    with pytest.raises(ValueError, match="after the aperture"):
        calculate(Setup(model="airy", **OPTICS, pulse_energy=1.0, measured="before_aperture"))
    with pytest.raises(ValueError, match="unknown model"):
        calculate(Setup(model="donut"))


def test_setup_file_units():
    setup = load_setup(EXAMPLE)
    assert setup.model == "truncated_gaussian"
    assert setup.wavelength == pytest.approx(800e-9)
    assert setup.beam_radius == pytest.approx(5e-3)
    assert setup.aperture_radius == pytest.approx(2.5e-3)
    assert setup.focal_length == pytest.approx(0.35)
    with pytest.raises(ValueError, match="unknown setting"):
        setup_from_dict({"beam": {"model": "airy", "diametre_mm": 1}})


def test_cli(tmp_path, capsys):
    out = tmp_path / "results.csv"
    assert main([str(EXAMPLE), "--csv", str(out)]) == 0
    text = capsys.readouterr().out
    assert "Truncated Gaussian" in text
    assert "fluence_peak" in text and "Assumptions" in text
    assert "spot_fwhm" in out.read_text(encoding="utf-8")
    assert main([str(tmp_path / "missing.toml")]) == 1
