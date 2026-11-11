"""Pulse energy, fluence definitions, intensity and scanning. SI units, no I/O."""

from __future__ import annotations

import math
from collections.abc import Iterable

from beamforge.beams import Spot

# Peak power = k * E / tau, tau = FWHM pulse duration.
# SPEC.md section 4 quotes the rounded values 0.94, 0.88 and 1.
PULSE_SHAPE_FACTORS = {
    "gaussian": 2.0 * math.sqrt(math.log(2.0) / math.pi),  # 0.9394
    "sech2": math.log(1.0 + math.sqrt(2.0)),  # 0.8814
    "rectangular": 1.0,
}


def pulse_energy(average_power: float, rep_rate: float) -> float:
    """Energy per pulse: E = P_avg / f_rep (SPEC.md section 4).

    Assumes all average power is in the pulse train (no pedestal or ASE).
    """
    return average_power / rep_rate


def total_transmission(transmissions: Iterable[float]) -> float:
    """Product of the transmissions of all elements between measurement and target."""
    total = 1.0
    for t in transmissions:
        if not 0.0 <= t <= 1.0:
            raise ValueError(f"transmission {t} is outside [0, 1]")
        total *= t
    return total


def gaussian_aperture_transmission(truncation_ratio: float) -> float:
    """Energy fraction of a Gaussian beam passing a centred circular aperture.

    Formula: 1 - exp(-2 T^2), T = a / w (SPEC.md section 4).
    Assumes an ideal Gaussian beam centred on the aperture.
    Reference: Siegman, *Lasers* (1986), sec. 17.1.
    """
    return -math.expm1(-2.0 * truncation_ratio**2)


def peak_fluence(energy: float, a_eff: float) -> float:
    """Peak fluence F0 = E / A_eff (SPEC.md section 4; ISO 21254-1 effective area)."""
    return energy / a_eff


def disc_average_fluence(energy: float, spot: Spot, radius: float) -> float:
    """Average fluence over a centred disc: E * (encircled fraction) / (pi R^2)."""
    return energy * spot.encircled_fraction(radius) / (math.pi * radius**2)


def fluence_definitions(energy: float, spot: Spot) -> dict[str, float]:
    """All fluence values the tool reports, keyed by an explicit definition name.

    - ``peak``: F0 = E / A_eff, the maximum of the fluence distribution.
    - ``average_fwhm_disc``: energy inside the FWHM-diameter disc / its area.
    - ``average_1e2_disc``: energy inside the disc whose radius is where the
      intensity falls to exp(-2) of the peak / its area.
    - ``gaussian_equivalent``: 2 E / (pi w^2) with w that same exp(-2) radius,
      i.e. what the ideal-Gaussian formula gives for the measured 1/e^2 radius
      (J. M. Liu, Opt. Lett. 7, 196 (1982)). Equal to ``peak`` only for a
      Gaussian spot.
    """
    r_half = spot.fwhm / 2.0
    r_e2 = spot.radius_1e2
    return {
        "peak": peak_fluence(energy, spot.a_eff),
        "average_fwhm_disc": disc_average_fluence(energy, spot, r_half),
        "average_1e2_disc": disc_average_fluence(energy, spot, r_e2),
        "gaussian_equivalent": 2.0 * energy / (math.pi * r_e2**2),
    }


def peak_intensity(fluence: float, pulse_duration: float, pulse_shape: str = "gaussian") -> float:
    """Peak intensity I0 = k F0 / tau (SPEC.md section 4).

    tau is the FWHM pulse duration; k = 2 sqrt(ln 2 / pi) = 0.9394 (Gaussian),
    ln(1 + sqrt 2) = 0.8814 (sech^2), 1 (rectangular). k follows from
    integrating the temporal shape. Assumes space and time are separable.
    Reference: J.-C. Diels and W. Rudolph, *Ultrashort Laser Pulse Phenomena*,
    2nd ed., table 1.1.
    """
    try:
        k = PULSE_SHAPE_FACTORS[pulse_shape]
    except KeyError:
        raise ValueError(
            f"unknown pulse shape {pulse_shape!r}; use one of {sorted(PULSE_SHAPE_FACTORS)}"
        ) from None
    return k * fluence / pulse_duration


def pulses_per_spot(spot_diameter: float, rep_rate: float, scan_speed: float) -> float:
    """Pulses per spot N = d f_rep / v (SPEC.md section 4).

    d is the spot diameter in whichever definition the caller states.
    """
    return spot_diameter * rep_rate / scan_speed


def pulse_overlap(spot_diameter: float, rep_rate: float, scan_speed: float) -> float:
    """Pulse-to-pulse overlap = 1 - v / (f_rep d) (SPEC.md section 4).

    Negative values mean consecutive spots are separated.
    """
    return 1.0 - scan_speed / (rep_rate * spot_diameter)
