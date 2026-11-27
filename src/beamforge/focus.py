"""The spot away from focus: Fresnel propagation behind the lens, best focus, Rayleigh length.

All quantities are SI (metres). No I/O happens here. The focal-plane models in
:mod:`beamforge.beams` are the special case z = f of the field computed here.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass
from functools import cached_property, lru_cache

import numpy as np
from scipy import optimize, special

from beamforge.beams import DIFFRACTION_ASSUMPTIONS, Spot, check_positive

# 600-point Gauss-Legendre rule on [0, 1] for the radial integral over the aperture.
_X, _W = np.polynomial.legendre.leggauss(600)
NODES = 0.5 * (_X + 1.0)
WEIGHTS = 0.5 * _W
PEAK_GRID_STEP = 0.2  # first search for an off-axis maximum, in the dimensionless radius x


def axial_integral(c: complex) -> complex:
    """Closed form of integral_0^1 exp(c s^2) s ds = (e^c - 1) / (2c), and 1/2 at c = 0."""
    if abs(c) < 1e-8:
        return 0.5 + c / 4.0
    return (cmath.exp(c) - 1.0) / (2.0 * c)


@dataclass(frozen=True)
class FresnelSpot(Spot):
    """Spot of a beam limited by a circular aperture, in any plane behind the lens.

    Paraxial (Fresnel) diffraction behind an ideal thin lens with the aperture at
    the lens. With z the distance from the lens to the target plane, a the
    aperture radius, s = r / a and

        x   = 2 pi a rho / (lambda z)            (dimensionless radius on target)
        psi = pi a^2 (1/z - 1/f) / lambda        (defocus phase at the aperture edge)
        g(x) = integral_0^1 A(s) exp(i psi s^2) J0(x s) s ds,

    the field is U(rho, z) = (2 pi a^2 / (lambda z)) g(x), with A(s) = exp(-T^2 s^2)
    for a Gaussian beam of 1/e^2 intensity radius w (T = a / w) and A(s) = 1 for
    uniform illumination. With I = |U|^2 and the power P = 2 pi a^2 p,
    p = integral_0^1 A(s)^2 s ds, the effective area is

        A_eff = P / I_max = lambda^2 z^2 p / (2 pi a^2 max_x |g(x)|^2).

    At z = f (psi = 0) these are the focal-plane formulas of ``TruncatedGaussianSpot``
    and ``AirySpot``. g is evaluated with a 600-point Gauss-Legendre rule. I_max is
    the larger of the on-axis value (closed form, see ``axial_integral``) and the
    maximum over a grid of radii, refined numerically, so a ring-shaped spot far
    from focus is handled; ``centre_is_peak`` tells which case applies.

    Assumptions: scalar, paraxial, ideal thin lens, flat input phase, centred
    circular aperture at the lens, Fresnel propagation from the lens to the target.

    References: J. W. Goodman, *Introduction to Fourier Optics*, 3rd ed. (2005),
    ch. 4 and 5 (Fresnel diffraction, lens as a phase transformation);
    M. Born and E. Wolf, *Principles of Optics*, 7th ed., sec. 8.8 (light
    distribution near focus).
    """

    wavelength: float
    focal_length: float
    aperture_radius: float
    distance: float
    input_radius: float | None = None

    def __post_init__(self) -> None:
        for name in ("wavelength", "focal_length", "aperture_radius", "distance"):
            check_positive(name, getattr(self, name))
        if self.input_radius is not None:
            check_positive("input_radius", self.input_radius)

    @property
    def name(self) -> str:
        if self.input_radius is None:
            return "Uniform circular aperture (Airy)"
        return "Truncated Gaussian"

    @property
    def assumptions(self) -> tuple[str, ...]:
        if self.input_radius is None:
            model = ("uniform illumination of the aperture",)
        else:
            model = ("ideal Gaussian input (M^2 = 1), centred circular aperture at the lens",)
        return (
            DIFFRACTION_ASSUMPTIONS
            + model
            + ("Fresnel propagation to the target, its distance measured from best focus",)
        )

    @property
    def _t2(self) -> float:
        if self.input_radius is None:
            return 0.0
        return (self.aperture_radius / self.input_radius) ** 2

    @property
    def _psi(self) -> float:
        a2 = self.aperture_radius**2
        return math.pi * a2 * (1.0 / self.distance - 1.0 / self.focal_length) / self.wavelength

    @property
    def _c(self) -> complex:
        return complex(-self._t2, self._psi)

    @property
    def _scale(self) -> float:
        return self.wavelength * self.distance / (2.0 * math.pi * self.aperture_radius)

    @property
    def _p(self) -> float:
        t2 = self._t2
        if t2 < 1e-12:
            return 0.5
        return -math.expm1(-2.0 * t2) / (4.0 * t2)

    def _g(self, x: np.ndarray) -> np.ndarray:
        """g(x) for an array of dimensionless radii, by Gauss-Legendre quadrature."""
        weights = WEIGHTS * NODES * np.exp(self._c * NODES**2)
        return special.j0(np.outer(x, NODES)) @ weights

    @cached_property
    def _peak(self) -> tuple[float, float]:
        """(max |g|^2, x where it occurs). x = 0 when the centre is the brightest point."""
        axis = abs(axial_integral(self._c)) ** 2
        x_max = max(40.0, 3.0 * abs(self._psi) + 20.0)
        grid = np.arange(0.0, x_max + PEAK_GRID_STEP, PEAK_GRID_STEP)
        values = np.abs(self._g(grid)) ** 2
        k = int(np.argmax(values[1:])) + 1  # brightest grid point off the axis
        if values[k] < 0.95 * axis:
            return axis, 0.0
        # A ring may be as bright as the centre: locate its maximum exactly.
        lo, hi = grid[k - 1], grid[min(k + 1, len(grid) - 1)]
        best = optimize.minimize_scalar(
            lambda x: -(abs(self._g(np.array([x]))[0]) ** 2),
            bounds=(lo, hi),
            method="bounded",
            options={"xatol": 1e-9},
        )
        ring = max(-best.fun, values[k])
        if ring <= axis * (1.0 + 1e-9):
            return axis, 0.0
        return ring, float(best.x) if -best.fun >= values[k] else float(grid[k])

    @property
    def centre_is_peak(self) -> bool:
        """True when the brightest point of the spot is its centre."""
        return self._peak[1] == 0.0

    @property
    def _peak_radius(self) -> float:
        return self._peak[1] * self._scale

    def radius_at_level(self, level: float) -> float:
        """As :meth:`Spot.radius_at_level`, with the outward steps evaluated in batches.

        Same steps (1/20 of the scale length from the brightest point) and the same
        first crossing as the base class, refined with Brent's method; evaluating
        128 radii per call only makes it faster.
        """
        if not 0.0 < level < 1.0:
            raise ValueError("level must be between 0 and 1")
        step = self._scale / 20.0
        start = self._peak_radius
        for batch in range(800):
            radii = start + step * np.arange(batch * 128 + 1, batch * 128 + 129)
            below = np.flatnonzero(self.profile(radii) < level)
            if below.size:
                hi = float(radii[below[0]])
                return optimize.brentq(lambda x: float(self.profile(x)) - level, hi - step, hi)
        raise RuntimeError("profile never falls below the requested level")

    def profile(self, rho):
        rho = np.asarray(rho, dtype=float)
        x = np.abs(rho).ravel() / self._scale
        values = np.abs(self._g(x)) ** 2 / self._peak[0]
        return values.reshape(rho.shape)

    @property
    def a_eff(self) -> float:
        return (
            (self.wavelength * self.distance) ** 2
            * self._p
            / (2.0 * math.pi * self.aperture_radius**2 * self._peak[0])
        )

    @property
    def axial_a_eff(self) -> float:
        """P / I(0): equals ``a_eff`` whenever the centre is the brightest point.

        Closed form from ``axial_integral``, so it is cheap to evaluate many times.
        """
        axis = abs(axial_integral(self._c)) ** 2
        return (
            (self.wavelength * self.distance) ** 2
            * self._p
            / (2.0 * math.pi * self.aperture_radius**2 * axis)
        )


def _pupil_depth(wavelength: float, focal_length: float, radius: float) -> float:
    """Length scale lambda f^2 / (pi r^2) of the focal region for a pupil of radius r.

    For a Gaussian beam of input radius r this is its Rayleigh range (Siegman,
    *Lasers*, ch. 17); for a uniform aperture of radius r the axial intensity first
    vanishes at 2 pi times this distance (Born and Wolf, sec. 8.8). Used only to
    choose search ranges and step sizes.
    """
    return wavelength * focal_length**2 / (math.pi * radius**2)


@lru_cache(maxsize=512)
def best_focus_distance(
    wavelength: float,
    focal_length: float,
    aperture_radius: float,
    input_radius: float | None = None,
) -> float:
    """Distance from the lens of best focus: the plane of highest peak intensity.

    Near focus the brightest point is on the axis, where the Fresnel integral of
    ``FresnelSpot`` has the closed form I(0, z) = (2 pi a^2 / (lambda z))^2
    |(e^c - 1) / (2c)|^2, c = -T^2 + i psi(z). Its maximum is found numerically
    within +-2 L of the geometric focus, L = ``_pupil_depth`` for the smaller of the
    aperture and beam radii, which lies inside the main axial lobe. For a Fresnel
    number a^2 / (lambda f) much larger than 1 the best focus lies slightly closer
    to the lens than f: the focal shift.

    References: Y. Li and E. Wolf, Opt. Commun. 39, 211 (1981) (focal shift);
    Born and Wolf, *Principles of Optics*, 7th ed., sec. 8.8.
    """
    radius = aperture_radius if input_radius is None else min(aperture_radius, input_radius)
    depth = _pupil_depth(wavelength, focal_length, radius)
    lo = max(focal_length - 2.0 * depth, 0.02 * focal_length)
    hi = focal_length + 2.0 * depth

    def minus_axial(z: float) -> float:
        spot = FresnelSpot(wavelength, focal_length, aperture_radius, z, input_radius)
        return -1.0 / spot.axial_a_eff

    best = optimize.minimize_scalar(
        minus_axial, bounds=(lo, hi), method="bounded", options={"xatol": 1e-9 * focal_length}
    )
    z = float(best.x)
    if min(z - lo, hi - z) < 1e-3 * (hi - lo):
        raise ValueError(
            f"no clear focus: the Fresnel number a^2/(lambda f) = "
            f"{aperture_radius**2 / (wavelength * focal_length):.3g} is too small"
        )
    return z


def aperture_rayleigh_lengths(
    wavelength: float,
    focal_length: float,
    aperture_radius: float,
    input_radius: float | None = None,
) -> tuple[float, float]:
    """Rayleigh lengths of an aperture-limited beam, toward and away from the lens.

    Definition used by the tool: the distance from best focus at which the peak
    fluence E / A_eff falls to half its best-focus value, i.e. A_eff doubles. For a
    Gaussian beam this is the Rayleigh range z_R = pi w0^2 / lambda (Siegman,
    *Lasers*, ch. 17); for a clipped beam the two directions differ slightly.

    Found by stepping outwards from best focus in steps of L / 8 (L as in
    ``best_focus_distance``) and refining with Brent's method, first with the
    closed-form on-axis A_eff, then with the full A_eff if the spot there is not
    brightest at its centre. Returns positive distances (toward, away) in metres.
    """
    best = best_focus_distance(wavelength, focal_length, aperture_radius, input_radius)
    radius = aperture_radius if input_radius is None else min(aperture_radius, input_radius)
    step = _pupil_depth(wavelength, focal_length, radius) / 8.0

    def spot(d: float) -> FresnelSpot:
        return FresnelSpot(wavelength, focal_length, aperture_radius, best + d, input_radius)

    def find(a_eff, sign: float) -> float:
        target = 2.0 * a_eff(0.0)
        d = 0.0
        for _ in range(4000):
            nxt = d + sign * step
            if best + nxt <= 0.0:
                break
            if a_eff(nxt) >= target:
                return abs(optimize.brentq(lambda x: a_eff(x) - target, d, nxt, xtol=1e-12))
            d = nxt
        raise ValueError("the peak fluence never falls to half within the paraxial range")

    lengths = []
    for sign in (-1.0, 1.0):
        length = find(lambda d: spot(d).axial_a_eff, sign)
        if not spot(sign * length).centre_is_peak:
            length = find(lambda d: spot(d).a_eff, sign)
        lengths.append(length)
    return lengths[0], lengths[1]
