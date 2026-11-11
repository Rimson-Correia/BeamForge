"""Beam models: the intensity profile of the spot on target.

Every model is a radially symmetric profile ``I(rho) / I_max`` with an effective
area ``A_eff``. All quantities are SI (metres). No I/O happens here.

Common assumptions of the diffraction models (SPEC.md section 1): scalar field,
paraxial focusing (NA << 1), ideal aberration-free thin lens, target in the focal
plane unless a model says otherwise.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
from scipy import integrate, optimize, special

DIFFRACTION_ASSUMPTIONS = (
    "scalar diffraction (no polarisation effects)",
    "paraxial focusing (NA << 1)",
    "ideal aberration-free thin lens",
)

E2_LEVEL = math.exp(-2.0)


def gaussian_radius_from_diameter(diameter: float, definition: str) -> float:
    """Convert a Gaussian beam diameter to the 1/e^2 intensity radius w.

    Formula: I(r) = I0 exp(-2 r^2 / w^2), so
    ``"1/e2"``: w = d / 2;  ``"fwhm"``: w = d / sqrt(2 ln 2).

    Assumes an ideal Gaussian profile.
    Reference: A. E. Siegman, *Lasers* (University Science Books, 1986), ch. 17.
    """
    if definition == "1/e2":
        return diameter / 2.0
    if definition == "fwhm":
        return diameter / math.sqrt(2.0 * math.log(2.0))
    raise ValueError(f"unknown diameter definition {definition!r}; use '1/e2' or 'fwhm'")


class Spot(ABC):
    """A radially symmetric spot on target."""

    name: str
    assumptions: tuple[str, ...]

    @abstractmethod
    def profile(self, rho):
        """Normalised intensity I(rho) / I_max at radius ``rho`` (m)."""

    @property
    @abstractmethod
    def a_eff(self) -> float:
        """Effective area A_eff = integral of I / I_max over the target plane (m^2).

        Reference for the definition: ISO 21254-1:2011 (effective area).
        """

    @property
    @abstractmethod
    def _scale(self) -> float:
        """A characteristic radius (m) used to step outwards when root finding."""

    def radius_at_level(self, level: float) -> float:
        """Smallest radius where I / I_max falls to ``level`` (0 < level < 1).

        Found numerically: step outwards from the centre until the profile drops
        below ``level``, then refine with Brent's method. For profiles with side
        lobes this is the crossing inside the main lobe.
        """
        if not 0.0 < level < 1.0:
            raise ValueError("level must be between 0 and 1")
        step = self._scale / 20.0
        r = 0.0
        for _ in range(100_000):
            if float(self.profile(r + step)) < level:
                return optimize.brentq(lambda x: float(self.profile(x)) - level, r, r + step)
            r += step
        raise RuntimeError("profile never falls below the requested level")

    @property
    def fwhm(self) -> float:
        """Full width at half maximum of the intensity profile (m)."""
        return 2.0 * self.radius_at_level(0.5)

    @property
    def radius_1e2(self) -> float:
        """Radius where the intensity falls to exp(-2) of its peak (m)."""
        return self.radius_at_level(E2_LEVEL)

    def encircled_fraction(self, radius: float) -> float:
        """Fraction of the on-target energy inside a centred disc of ``radius``.

        Formula: (1 / A_eff) * integral_0^R [I(rho) / I_max] 2 pi rho d rho,
        evaluated numerically. Follows directly from the definition of A_eff.
        """
        value, _ = integrate.quad(
            lambda r: float(self.profile(r)) * 2.0 * math.pi * r, 0.0, radius, limit=200
        )
        return value / self.a_eff


@dataclass(frozen=True)
class GaussianSpot(Spot):
    """Focused Gaussian beam, ideal (M^2 = 1) or real (M^2 > 1), no clipping.

    Formulas (SPEC.md section 4):
        w0  = M^2 lambda f / (pi w)          waist radius in the focal plane
        z_R = pi w0^2 / (M^2 lambda)         Rayleigh range
        w(z) = w0 sqrt(1 + (z / z_R)^2)      radius at distance z from focus
        I(rho) / I_max = exp(-2 rho^2 / w(z)^2)
        A_eff = pi w(z)^2 / 2,  FWHM = w(z) sqrt(2 ln 2)

    Assumptions: collimated input beam with its waist at the lens and an input
    Rayleigh range much longer than f; ideal thin lens; paraxial. For M^2 > 1 the
    profile is treated as the "embedded Gaussian" scaled by M^2, which is an
    approximation because a beam with M^2 > 1 is not exactly Gaussian.

    References: A. E. Siegman, *Lasers* (1986), ch. 17; ISO 11146-1:2021 for M^2.
    """

    wavelength: float
    focal_length: float
    input_radius: float
    m2: float = 1.0
    defocus: float = 0.0

    def __post_init__(self) -> None:
        if self.m2 < 1.0:
            raise ValueError("M^2 cannot be smaller than 1")

    @property
    def name(self) -> str:
        return "Ideal Gaussian" if self.m2 == 1.0 else "Gaussian with M^2"

    @property
    def assumptions(self) -> tuple[str, ...]:
        base = (
            "paraxial focusing (NA << 1)",
            "ideal aberration-free thin lens",
            "collimated input, beam not clipped by any aperture",
        )
        if self.m2 != 1.0:
            base += ("embedded-Gaussian profile scaled by M^2 (approximation)",)
        return base

    @property
    def waist_radius(self) -> float:
        return self.m2 * self.wavelength * self.focal_length / (math.pi * self.input_radius)

    @property
    def rayleigh_range(self) -> float:
        return math.pi * self.waist_radius**2 / (self.m2 * self.wavelength)

    @property
    def radius(self) -> float:
        """1/e^2 intensity radius w(z) at the target."""
        return self.waist_radius * math.sqrt(1.0 + (self.defocus / self.rayleigh_range) ** 2)

    def profile(self, rho):
        return np.exp(-2.0 * np.asarray(rho, dtype=float) ** 2 / self.radius**2)

    @property
    def a_eff(self) -> float:
        return math.pi * self.radius**2 / 2.0

    @property
    def _scale(self) -> float:
        return self.radius

    def radius_at_level(self, level: float) -> float:
        """Analytic: rho = w sqrt(-ln(level) / 2)."""
        if not 0.0 < level < 1.0:
            raise ValueError("level must be between 0 and 1")
        return self.radius * math.sqrt(-math.log(level) / 2.0)

    def encircled_fraction(self, radius: float) -> float:
        """Analytic: 1 - exp(-2 R^2 / w^2) (Siegman, *Lasers*, ch. 17)."""
        return -math.expm1(-2.0 * radius**2 / self.radius**2)


@dataclass(frozen=True)
class AirySpot(Spot):
    """Focal spot of a uniformly illuminated circular aperture (Airy pattern).

    Formulas (SPEC.md section 4), with a the aperture radius and NA ~ a / f:
        I(x) / I_max = [2 J1(x) / x]^2,   x = 2 pi a rho / (lambda f)
        FWHM = 0.5145 lambda / NA
        first dark ring diameter = 1.22 lambda / NA
        A_eff = lambda^2 f^2 / (pi a^2)
        encircled energy = 1 - J0(x)^2 - J1(x)^2

    Assumptions: perfectly flat illumination of the aperture, focal plane only,
    scalar, paraxial, ideal lens.

    Reference: M. Born and E. Wolf, *Principles of Optics*, 7th ed., sec. 8.5.2.
    """

    wavelength: float
    focal_length: float
    aperture_radius: float

    name = "Uniform circular aperture (Airy)"
    assumptions = DIFFRACTION_ASSUMPTIONS + (
        "uniform illumination of the aperture",
        "target in the focal plane",
    )

    def _x(self, rho):
        return (
            2.0
            * math.pi
            * self.aperture_radius
            * np.abs(np.asarray(rho, dtype=float))
            / (self.wavelength * self.focal_length)
        )

    def profile(self, rho):
        x = self._x(rho)
        safe = np.where(x == 0.0, 1.0, x)
        return np.where(x == 0.0, 1.0, (2.0 * special.j1(safe) / safe) ** 2)

    @property
    def a_eff(self) -> float:
        return (self.wavelength * self.focal_length) ** 2 / (math.pi * self.aperture_radius**2)

    @property
    def _scale(self) -> float:
        return self.wavelength * self.focal_length / (2.0 * math.pi * self.aperture_radius)

    @property
    def first_dark_ring_diameter(self) -> float:
        """Diameter of the first zero: (j_{1,1} / pi) lambda f / a = 1.2197 lambda / NA."""
        first_zero = special.jn_zeros(1, 1)[0]
        return 2.0 * first_zero * self._scale

    def encircled_fraction(self, radius: float) -> float:
        x = float(self._x(radius))
        return 1.0 - special.j0(x) ** 2 - special.j1(x) ** 2


@dataclass(frozen=True)
class TruncatedGaussianSpot(Spot):
    """Focal spot of a Gaussian beam clipped by a centred circular aperture.

    With w the input 1/e^2 intensity radius, a the aperture radius and
    T = a / w the truncation ratio (SPEC.md section 4):
        U(rho) ~ integral_0^a exp(-r^2 / w^2) J0(2 pi r rho / (lambda f)) r dr
        I(rho) / I_max = |U(rho) / U(0)|^2
        A_eff = lambda^2 f^2 (1 - e^(-2T^2)) / [2 pi w^2 (1 - e^(-T^2))^2]
    The integral is evaluated numerically in the dimensionless form
        U(x) = integral_0^1 exp(-T^2 s^2) J0(x s) s ds,  x = 2 pi a rho / (lambda f),
    with U(0) = (1 - e^(-T^2)) / (2 T^2). FWHM is a numerical root of
    I / I_max = 0.5. Limits: T -> infinity gives the Gaussian focus, T -> 0 the
    Airy pattern.

    Assumptions: ideal Gaussian input (M^2 = 1) with a flat phase, aperture at
    the lens and centred on the beam, focal plane only, scalar, paraxial, ideal
    lens.

    References: H. Urey, Appl. Opt. 43, 620 (2004); Z. L. Horvath and Z. Bor,
    Opt. Commun. 222, 51 (2003).
    """

    wavelength: float
    focal_length: float
    input_radius: float
    aperture_radius: float

    name = "Truncated Gaussian"
    assumptions = DIFFRACTION_ASSUMPTIONS + (
        "ideal Gaussian input (M^2 = 1), centred circular aperture at the lens",
        "target in the focal plane",
    )

    @property
    def truncation_ratio(self) -> float:
        return self.aperture_radius / self.input_radius

    @property
    def _scale(self) -> float:
        return self.wavelength * self.focal_length / (2.0 * math.pi * self.aperture_radius)

    def profile(self, rho):
        t = self.truncation_ratio
        u0 = -math.expm1(-(t**2)) / (2.0 * t**2)

        def one(x: float) -> float:
            value, _ = integrate.quad(
                lambda s: math.exp(-((t * s) ** 2)) * special.j0(x * s) * s, 0.0, 1.0, limit=200
            )
            return (value / u0) ** 2

        x = np.abs(np.asarray(rho, dtype=float)) / self._scale
        return np.vectorize(one, otypes=[float])(x)

    @property
    def a_eff(self) -> float:
        t2 = self.truncation_ratio**2
        return (
            (self.wavelength * self.focal_length) ** 2
            * -math.expm1(-2.0 * t2)
            / (2.0 * math.pi * self.input_radius**2 * math.expm1(-t2) ** 2)
        )


@dataclass(frozen=True)
class FlatTopSpot(Spot):
    """Flat-top (top-hat) spot of given diameter on target, e.g. an imaged beam.

    Formulas (SPEC.md section 4): A = pi d^2 / 4, F = E / A, uniform inside d.
    Assumption: perfectly uniform fluence with sharp edges.
    """

    diameter: float

    name = "Flat-top at target"
    assumptions = ("perfectly uniform fluence inside the stated diameter, sharp edges",)

    def profile(self, rho):
        return np.where(np.abs(np.asarray(rho, dtype=float)) <= self.diameter / 2.0, 1.0, 0.0)

    @property
    def a_eff(self) -> float:
        return math.pi * self.diameter**2 / 4.0

    @property
    def _scale(self) -> float:
        return self.diameter / 2.0

    def radius_at_level(self, level: float) -> float:
        """Every level is crossed at the edge, rho = d / 2."""
        return self.diameter / 2.0

    def encircled_fraction(self, radius: float) -> float:
        return min(1.0, (2.0 * radius / self.diameter) ** 2)


def sample_profile(spot: Spot, points: int = 200, extent: float = 3.0):
    """Sample I / I_max on ``points`` radii from 0 to ``extent`` x the 1/e^2 radius.

    Returns ``(radii, values)`` as arrays, for plotting. No physics beyond
    evaluating ``spot.profile``.
    """
    radii = np.linspace(0.0, extent * spot.radius_1e2, points)
    return radii, np.asarray(spot.profile(radii), dtype=float)


def edge_intensity(truncation_ratio: float) -> float:
    """Intensity at the aperture edge relative to the beam centre: exp(-2 T^2).

    Gaussian input I(r) = I0 exp(-2 r^2 / w^2) evaluated at r = a, T = a / w.
    Reference: Siegman, *Lasers* (1986), sec. 17.1.
    """
    return math.exp(-2.0 * truncation_ratio**2)


def model_warnings(model: str, truncation_ratio: float | None) -> list[str]:
    """Warn when the chosen model does not fit the aperture (SPEC.md section 3).

    Criteria (tool defaults, stated in the message):
    - Gaussian models: warn if T = a / w < 2.3. An aperture of diameter 4.6 w is
      needed to keep diffraction ripple near 1 % (Siegman, *Lasers*, sec. 17.1).
    - Airy model: warn if the intensity at the aperture edge is below 80 % of
      the centre, i.e. the illumination is not close to uniform.
    """
    if truncation_ratio is None:
        return []
    t = truncation_ratio
    if model == "gaussian" and t < 2.3:
        return [
            f"Aperture clips the beam (T = a/w = {t:.3g} < 2.3, clipped energy "
            f"{edge_intensity(t):.2%}); the Gaussian model ignores this. "
            "Consider the truncated_gaussian model."
        ]
    if model == "airy" and edge_intensity(t) < 0.8:
        return [
            f"Illumination is not uniform (edge intensity {edge_intensity(t):.3g} of centre, "
            f"T = {t:.3g}); the Airy model assumes flat illumination. "
            "Consider the truncated_gaussian model."
        ]
    return []
