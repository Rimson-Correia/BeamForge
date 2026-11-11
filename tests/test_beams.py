"""Beam models against the SPEC.md section 5 validation table and analytic limits."""

import math

import pytest

from beamforge.beams import (
    AirySpot,
    FlatTopSpot,
    GaussianSpot,
    Spot,
    TruncatedGaussianSpot,
    edge_intensity,
    gaussian_radius_from_diameter,
    model_warnings,
)
from beamforge.energy import gaussian_aperture_transmission

# Reference setup: 800 nm, f = 350 mm, input 1/e^2 diameter 10 mm, aperture 5 mm.
LAM, F, W, A = 800e-9, 0.350, 5e-3, 2.5e-3
UM = 1e-6
SPEC = pytest.approx  # spec values are given to 4 significant figures


def test_airy_validation_table():
    spot = AirySpot(LAM, F, A)
    assert spot.fwhm / UM == SPEC(57.62, rel=5e-4)
    assert spot.first_dark_ring_diameter / UM == SPEC(136.6, rel=5e-4)
    assert spot.a_eff / UM**2 == SPEC(3993, rel=5e-4)


def test_truncated_gaussian_validation_table():
    spot = TruncatedGaussianSpot(LAM, F, W, A)
    assert spot.fwhm / UM == SPEC(58.94, rel=5e-4)
    assert spot.a_eff / UM**2 == SPEC(4014, rel=5e-4)
    assert edge_intensity(spot.truncation_ratio) == SPEC(0.6065, rel=5e-4)
    assert gaussian_aperture_transmission(spot.truncation_ratio) == SPEC(0.3935, rel=5e-4)


def test_truncated_gaussian_limit_large_t_is_gaussian():
    truncated = TruncatedGaussianSpot(LAM, F, W, 5 * W)
    gauss = GaussianSpot(LAM, F, W)
    assert truncated.fwhm == pytest.approx(gauss.fwhm, rel=1e-6)
    assert truncated.a_eff == pytest.approx(gauss.a_eff, rel=1e-6)


def test_truncated_gaussian_limit_small_t_is_airy():
    truncated = TruncatedGaussianSpot(LAM, F, 100 * A, A)
    airy = AirySpot(LAM, F, A)
    assert truncated.fwhm == pytest.approx(airy.fwhm, rel=1e-4)
    assert truncated.a_eff == pytest.approx(airy.a_eff, rel=1e-4)


def test_truncated_gaussian_a_eff_matches_numerical_integral():
    # A_eff is by definition the integral of the profile. The diffraction rings
    # carry energy far out (residual ~ 1/radius), so 20 FWHM leaves about 1 %.
    spot = TruncatedGaussianSpot(LAM, F, W, A)
    assert Spot.encircled_fraction(spot, 20 * spot.fwhm) == pytest.approx(1.0, abs=2e-2)


def test_ideal_gaussian_analytic():
    spot = GaussianSpot(LAM, F, W)
    w0 = LAM * F / (math.pi * W)  # 17.83 um
    assert spot.waist_radius == pytest.approx(w0)
    assert spot.waist_radius / UM == pytest.approx(17.83, rel=5e-4)
    assert spot.fwhm == pytest.approx(w0 * math.sqrt(2 * math.log(2)))
    assert spot.a_eff == pytest.approx(math.pi * w0**2 / 2)
    assert spot.rayleigh_range == pytest.approx(math.pi * w0**2 / LAM)
    assert spot.radius_1e2 == pytest.approx(w0)
    # Half of the energy is inside the FWHM disc, 1 - e^-2 inside the 1/e^2 disc.
    assert spot.encircled_fraction(spot.fwhm / 2) == pytest.approx(0.5)
    assert spot.encircled_fraction(w0) == pytest.approx(1 - math.exp(-2))
    # The generic numerical routines agree with the analytic overrides.
    assert Spot.radius_at_level(spot, 0.5) == pytest.approx(spot.fwhm / 2)
    assert Spot.encircled_fraction(spot, w0) == pytest.approx(1 - math.exp(-2))


def test_gaussian_m2_and_defocus():
    ideal = GaussianSpot(LAM, F, W)
    real = GaussianSpot(LAM, F, W, m2=1.5)
    assert real.waist_radius == pytest.approx(1.5 * ideal.waist_radius)
    assert real.rayleigh_range == pytest.approx(1.5 * ideal.rayleigh_range)
    # One Rayleigh range from focus the radius grows by sqrt(2), the area doubles.
    out = GaussianSpot(LAM, F, W, defocus=ideal.rayleigh_range)
    assert out.radius == pytest.approx(math.sqrt(2) * ideal.waist_radius)
    assert out.a_eff == pytest.approx(2 * ideal.a_eff)
    with pytest.raises(ValueError):
        GaussianSpot(LAM, F, W, m2=0.9)


def test_airy_encircled_energy():
    spot = AirySpot(LAM, F, A)
    # 83.8 % of the energy is inside the first dark ring (Born & Wolf sec. 8.5.2).
    r1 = spot.first_dark_ring_diameter / 2
    assert spot.encircled_fraction(r1) == pytest.approx(0.838, abs=1e-3)
    assert Spot.encircled_fraction(spot, r1) == pytest.approx(spot.encircled_fraction(r1), rel=1e-6)
    assert float(spot.profile(r1)) == pytest.approx(0.0, abs=1e-12)


def test_flat_top():
    spot = FlatTopSpot(100e-6)
    assert spot.a_eff == pytest.approx(math.pi * (100e-6) ** 2 / 4)
    assert spot.fwhm == pytest.approx(100e-6)
    assert spot.encircled_fraction(25e-6) == pytest.approx(0.25)
    assert spot.encircled_fraction(80e-6) == 1.0


def test_diameter_definitions():
    assert gaussian_radius_from_diameter(10e-3, "1/e2") == pytest.approx(5e-3)
    fwhm = 5e-3 * math.sqrt(2 * math.log(2))
    assert gaussian_radius_from_diameter(fwhm, "fwhm") == pytest.approx(5e-3)
    with pytest.raises(ValueError):
        gaussian_radius_from_diameter(1.0, "1/e")


def test_model_warnings():
    assert model_warnings("gaussian", 0.5)  # clipped beam, Gaussian model chosen
    assert not model_warnings("gaussian", 3.0)
    assert model_warnings("airy", 0.5)  # edge at 61 %, not uniform
    assert not model_warnings("airy", 0.1)
    assert not model_warnings("truncated_gaussian", 0.5)
    assert not model_warnings("gaussian", None)
