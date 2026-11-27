"""Through focus: Fresnel propagation, best focus and Rayleigh length against known results."""

import math

import numpy as np
import pytest
from scipy import integrate, special

from beamforge.beams import AirySpot, GaussianSpot, TruncatedGaussianSpot
from beamforge.calculator import Setup, calculate, through_focus
from beamforge.focus import FresnelSpot, aperture_rayleigh_lengths, best_focus_distance

LAM, F, W, A = 800e-9, 0.350, 5e-3, 2.5e-3
UM = 1e-6


@pytest.mark.parametrize(
    "fresnel, focal",
    [
        (FresnelSpot(LAM, F, A, F, W), TruncatedGaussianSpot(LAM, F, W, A)),
        (FresnelSpot(LAM, F, A, F), AirySpot(LAM, F, A)),
    ],
)
def test_focal_plane_is_the_focal_plane_model(fresnel, focal):
    rho = np.array([0.0, 10, 29.4684, 70, 95, 140]) * UM
    assert fresnel.profile(rho) == pytest.approx(focal.profile(rho), abs=1e-12)
    assert fresnel.a_eff == pytest.approx(focal.a_eff, rel=1e-12)
    assert fresnel.fwhm == pytest.approx(focal.fwhm, rel=1e-9)
    assert fresnel.radius_1e2 == pytest.approx(focal.radius_1e2, rel=1e-9)


@pytest.mark.parametrize("dz, rho", [(-8e-3, 20 * UM), (6e-3, 47 * UM), (-20e-3, 60 * UM)])
def test_defocused_profile_matches_adaptive_quadrature(dz, rho):
    z = F + dz
    t2 = (A / W) ** 2
    psi = math.pi * A**2 * (1 / z - 1 / F) / LAM

    def g(x):
        def part(trig):
            return integrate.quad(
                lambda s: math.exp(-t2 * s * s) * trig(psi * s * s) * special.j0(x * s) * s,
                0.0,
                1.0,
                limit=400,
                epsabs=1e-14,
            )[0]

        return complex(part(math.cos), part(math.sin))

    x = 2 * math.pi * A * rho / (LAM * z)
    spot = FresnelSpot(LAM, F, A, z, W)
    assert spot.centre_is_peak
    assert float(spot.profile(rho)) == pytest.approx(abs(g(x)) ** 2 / abs(g(0.0)) ** 2, rel=1e-9)


def test_large_aperture_gives_the_gaussian_beam():
    """T = 6: the aperture does not matter and Gaussian-beam theory must come back."""
    big = 6 * W
    gauss = GaussianSpot(LAM, F, W)
    toward, away = aperture_rayleigh_lengths(LAM, F, big, W)
    assert toward == pytest.approx(gauss.rayleigh_range, rel=1e-4)
    assert away == pytest.approx(gauss.rayleigh_range, rel=1e-4)
    best = best_focus_distance(LAM, F, big, W)
    at_best = FresnelSpot(LAM, F, big, best, W)
    at_zr = FresnelSpot(LAM, F, big, best + away, W)
    assert at_zr.fwhm / at_best.fwhm == pytest.approx(math.sqrt(2), rel=1e-5)
    # Waist of a focused Gaussian beam lies before the focal plane by
    # f / (1 + (z_R,in / f)^2), z_R,in = pi w^2 / lambda (S. A. Self, Appl. Opt. 22, 658 (1983)).
    zr_in = math.pi * W**2 / LAM
    assert best - F == pytest.approx(-F / (1 + (zr_in / F) ** 2), rel=1e-3)


@pytest.mark.parametrize("a, rel", [(2.5e-3, 5e-3), (5e-3, 1e-3)])
def test_uniform_aperture_focal_shift_matches_li_and_wolf(a, rel):
    """Delta f / f = -1 / (1 + pi^2 N^2 / 12), N = a^2 / (lambda f), for N >> 1.

    Y. Li and E. Wolf, Opt. Commun. 39, 211 (1981).
    """
    n = a**2 / (LAM * F)
    shift = best_focus_distance(LAM, F, a) - F
    assert shift == pytest.approx(-F / (1 + math.pi**2 * n**2 / 12), rel=rel)


@pytest.mark.parametrize("u", [math.pi, 2 * math.pi, 3 * math.pi])
def test_uniform_aperture_axial_intensity_matches_born_and_wolf(u):
    """I(0, u) / I(0, 0) = [sin(u/4) / (u/4)]^2, u = 2 pi a^2 dz / (lambda f^2), for N >> 1.

    Born and Wolf, Principles of Optics, 7th ed., sec. 8.8. The Fresnel result
    approaches it as the Fresnel number grows; N = 1429 here.
    """
    a = 20e-3
    dz = u * LAM * F**2 / (2 * math.pi * a**2)
    ratio = FresnelSpot(LAM, F, a, F).a_eff / FresnelSpot(LAM, F, a, F + dz).a_eff
    assert ratio == pytest.approx((math.sin(u / 4) / (u / 4)) ** 2, abs=1e-3)


def test_ring_shaped_spot_is_detected_and_reported():
    dz = 2 * LAM * F**2 / A**2  # first axial zero of the uniform aperture, u = 4 pi
    spot = FresnelSpot(LAM, F, A, F + dz)
    assert not spot.centre_is_peak
    assert float(spot.profile(0.0)) < 0.5
    assert float(spot.profile(spot._peak_radius)) == pytest.approx(1.0)
    best = best_focus_distance(LAM, F, A)
    setup = Setup(model="airy", wavelength=LAM, focal_length=F, aperture_radius=A,
                  defocus=F + dz - best)  # fmt: skip
    assert any("ring-shaped" in w for w in calculate(setup).warnings)


def test_energy_is_conserved_away_from_focus():
    spot = FresnelSpot(LAM, F, A, F + 10e-3, W)
    assert spot.encircled_fraction(1e-3) == pytest.approx(1.0, abs=1.5e-2)


def test_reference_setup():
    """Regression values for the SPEC.md reference setup (not independent validation)."""
    best = best_focus_distance(LAM, F, A, W)
    toward, away = aperture_rayleigh_lengths(LAM, F, A, W)
    assert (best - F) * 1e3 == pytest.approx(-0.8522, abs=1e-3)
    assert toward * 1e3 == pytest.approx(13.19, abs=1e-2)
    assert away * 1e3 == pytest.approx(14.52, abs=1e-2)
    assert toward < away  # the clipped beam is not symmetric about best focus


def test_through_focus_table():
    setup = Setup(model="truncated_gaussian", wavelength=LAM, focal_length=F, beam_radius=W,
                  aperture_radius=A)  # fmt: skip
    scan = through_focus(setup, points=21)
    assert len(scan.distance) == 21
    assert 0.0 in scan.distance
    centre = int(np.argmin(np.abs(scan.distance)))
    assert scan.relative_peak_fluence[centre] == pytest.approx(1.0)
    assert scan.relative_peak_fluence.max() == pytest.approx(1.0, abs=1e-9)
    assert scan.relative_peak_fluence[0] < 0.5 and scan.relative_peak_fluence[-1] < 0.5
    half = Setup(**{**setup.__dict__, "defocus": scan.rayleigh_away_from_lens})
    assert build_ratio(setup, half) == pytest.approx(0.5, rel=1e-6)


def test_through_focus_any_range():
    setup = Setup(model="truncated_gaussian", wavelength=LAM, focal_length=F, beam_radius=W,
                  aperture_radius=A)  # fmt: skip
    scan = through_focus(setup, points=41, start=-50e-3, stop=50e-3)
    assert len(scan.distance) == 41
    assert scan.distance[0] == pytest.approx(-50e-3) and scan.distance[-1] == pytest.approx(50e-3)
    assert 0.0 in scan.distance
    assert not scan.centre_is_peak.all()  # rings far from focus
    beyond = through_focus(setup, points=5, start=5e-3, stop=9e-3)
    assert beyond.distance == pytest.approx([5e-3, 6e-3, 7e-3, 8e-3, 9e-3])
    with pytest.raises(ValueError, match="range"):
        through_focus(setup, start=5e-3, stop=-5e-3)
    with pytest.raises(ValueError, match="lens"):
        through_focus(setup, points=5, start=-0.5, stop=0.01)


def build_ratio(best, other):
    """Peak fluence of ``other`` relative to ``best`` for the same pulse energy."""
    one = calculate(Setup(**{**best.__dict__, "pulse_energy": 1e-6}))["fluence_peak"].value
    two = calculate(Setup(**{**other.__dict__, "pulse_energy": 1e-6}))["fluence_peak"].value
    return two / one


def test_rejects_impossible_input():
    with pytest.raises(ValueError):
        FresnelSpot(LAM, F, A, -1.0, W)
    with pytest.raises(ValueError):
        FresnelSpot(LAM, F, A, F, 0.0)
