"""Energy, fluence, intensity, scanning, uncertainty and measured-profile functions.

Power and energy values are arbitrary round numbers (SPEC.md section 5).
"""

import math

import numpy as np
import pytest

from beamforge import energy as en
from beamforge.beams import AirySpot, FlatTopSpot, GaussianSpot
from beamforge.measured import effective_area_from_image, fwhm_from_image
from beamforge.uncertainty import propagate_first_order, propagate_monte_carlo


def test_pulse_energy_and_transmission():
    assert en.pulse_energy(2.0, 1000.0) == pytest.approx(2e-3)
    assert en.total_transmission([0.5, 0.8]) == pytest.approx(0.4)
    assert en.total_transmission([]) == 1.0
    with pytest.raises(ValueError):
        en.total_transmission([1.2])


def test_fluence_definitions_gaussian():
    spot = GaussianSpot(800e-9, 0.35, 5e-3)
    w0 = spot.waist_radius
    fl = en.fluence_definitions(1e-3, spot)
    peak = 2 * 1e-3 / (math.pi * w0**2)
    assert fl["peak"] == pytest.approx(peak)
    assert fl["gaussian_equivalent"] == pytest.approx(peak)
    # Gaussian: FWHM-disc average = F0 / (2 ln 2), 1/e^2-disc average = F0 (1 - e^-2) / 2.
    assert fl["average_fwhm_disc"] == pytest.approx(peak / (2 * math.log(2)))
    assert fl["average_1e2_disc"] == pytest.approx(peak * (1 - math.exp(-2)) / 2)


def test_fluence_definitions_flat_top_and_airy():
    flat = en.fluence_definitions(1.0, FlatTopSpot(2.0))
    assert flat["peak"] == pytest.approx(1 / math.pi)
    assert flat["average_fwhm_disc"] == pytest.approx(flat["peak"])
    assert flat["gaussian_equivalent"] == pytest.approx(2 * flat["peak"])
    airy = en.fluence_definitions(1.0, AirySpot(800e-9, 0.35, 2.5e-3))
    assert airy["average_1e2_disc"] < airy["average_fwhm_disc"] < airy["peak"]


def test_peak_intensity_factors():
    assert en.peak_intensity(1.0, 1.0, "gaussian") == pytest.approx(0.9394, rel=1e-4)
    assert en.peak_intensity(1.0, 1.0, "sech2") == pytest.approx(0.8814, rel=1e-4)
    assert en.peak_intensity(3.0, 2.0, "rectangular") == pytest.approx(1.5)
    with pytest.raises(ValueError):
        en.peak_intensity(1.0, 1.0, "lorentzian")


def test_gaussian_factor_matches_numerical_integral():
    # Peak of a unit-energy Gaussian pulse with FWHM tau = 1.
    t = np.linspace(-10, 10, 200_001)
    shape = np.exp(-4 * math.log(2) * t**2)
    area = float(shape.sum() * (t[1] - t[0]))
    assert 1 / area == pytest.approx(en.PULSE_SHAPE_FACTORS["gaussian"], rel=1e-6)
    sech2 = 1 / np.cosh(2 * math.acosh(math.sqrt(2)) * t) ** 2
    area = float(sech2.sum() * (t[1] - t[0]))
    assert 1 / area == pytest.approx(en.PULSE_SHAPE_FACTORS["sech2"], rel=1e-6)


def test_scanning():
    assert en.pulses_per_spot(50e-6, 1000.0, 0.01) == pytest.approx(5.0)
    assert en.pulse_overlap(50e-6, 1000.0, 0.01) == pytest.approx(0.8)


def _fluence(energy, radius):
    return {"fluence": 2 * energy / (math.pi * radius**2)}


def test_first_order_uncertainty():
    values = {"energy": 1e-3, "radius": 20e-6}
    sigmas = {"energy": 0.02e-3, "radius": 0.2e-6}  # 2 % and 1 %
    value, sigma = propagate_first_order(_fluence, values, sigmas)["fluence"]
    assert value == pytest.approx(_fluence(**values)["fluence"])
    # Relative: sqrt(2 %^2 + (2 x 1 %)^2)
    assert sigma / value == pytest.approx(math.hypot(0.02, 0.02), rel=1e-5)


def test_monte_carlo_agrees_with_first_order():
    values = {"energy": 1e-3, "radius": 20e-6}
    sigmas = {"energy": 0.02e-3, "radius": 0.2e-6}
    value, sigma = propagate_monte_carlo(_fluence, values, sigmas, samples=20_000, seed=1)[
        "fluence"
    ]
    assert value == pytest.approx(_fluence(**values)["fluence"], rel=5e-3)
    assert sigma / value == pytest.approx(math.hypot(0.02, 0.02), rel=0.05)


def test_measured_profile_synthetic_gaussian():
    # Synthetic Gaussian spot, w = 20 px, 5 um pixels, 10x magnification, offset 7.
    w_px, pixel, mag = 20.0, 5e-6, 10.0
    y, x = np.mgrid[-150:151, -150:151]
    image = 1000 * np.exp(-2 * (x**2 + y**2) / w_px**2) + 7.0
    w = w_px * pixel / mag
    area = effective_area_from_image(image, pixel, mag, background=7.0)
    assert area == pytest.approx(math.pi * w**2 / 2, rel=1e-6)
    fx, fy = fwhm_from_image(image, pixel, mag, background=7.0)
    assert fx == pytest.approx(w * math.sqrt(2 * math.log(2)), rel=2e-3)
    assert fy == pytest.approx(fx)
