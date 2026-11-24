"""Turn a complete setup (SI values) into a labelled table of results. No I/O."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

from beamforge import energy as en
from beamforge.beams import (
    AirySpot,
    FlatTopSpot,
    GaussianSpot,
    Spot,
    check_positive,
    model_warnings,
)
from beamforge.focus import FresnelSpot, aperture_rayleigh_lengths, best_focus_distance

MODELS = ("gaussian", "truncated_gaussian", "airy", "flat_top")


@dataclass(frozen=True)
class Setup:
    """A full optical setup. All values in SI units; ``None`` means not given.

    ``beam_radius`` is the 1/e^2 intensity radius of the beam before the lens.
    Give exactly one of ``average_power`` (needs ``rep_rate``), ``pulse_energy``
    or ``target_peak_fluence`` (reverse direction), or none for optics only.
    ``measured`` says whether power/energy is measured ``"before_aperture"`` or
    ``"after_aperture"``; ``transmissions`` are the remaining elements up to the
    target. ``defocus`` is the distance of the target from best focus, negative
    toward the lens (for the Gaussian model best focus is the focal plane).
    """

    model: str
    wavelength: float | None = None
    focal_length: float | None = None
    beam_radius: float | None = None
    m2: float = 1.0
    aperture_radius: float | None = None
    defocus: float = 0.0
    flat_top_diameter: float | None = None
    rep_rate: float | None = None
    pulse_duration: float | None = None
    pulse_shape: str = "gaussian"
    average_power: float | None = None
    pulse_energy: float | None = None
    target_peak_fluence: float | None = None
    measured: str = "after_aperture"
    transmissions: tuple[float, ...] = ()
    scan_speed: float | None = None

    def __post_init__(self) -> None:
        """Reject values no real setup can have: zero or negative sizes, NaN, infinity."""
        for name in (
            "wavelength",
            "focal_length",
            "beam_radius",
            "aperture_radius",
            "flat_top_diameter",
            "rep_rate",
            "pulse_duration",
            "scan_speed",
        ):
            value = getattr(self, name)
            if value is not None:
                check_positive(name, value)
        for name in ("average_power", "pulse_energy", "target_peak_fluence"):
            value = getattr(self, name)
            if value is not None and not (math.isfinite(value) and value >= 0.0):
                raise ValueError(f"{name} must be zero or a positive number, got {value!r}")
        if not (math.isfinite(self.m2) and self.m2 >= 1.0):
            raise ValueError(f"M^2 must be a number of at least 1, got {self.m2!r}")
        if not math.isfinite(self.defocus):
            raise ValueError(f"defocus must be a finite number, got {self.defocus!r}")


@dataclass(frozen=True)
class Quantity:
    """One result row. ``value`` is SI; ``value * display_scale`` is in ``display_unit``."""

    name: str
    value: float
    unit: str
    display_scale: float
    display_unit: str
    definition: str

    @property
    def display_value(self) -> float:
        return self.value * self.display_scale


@dataclass(frozen=True)
class Result:
    model: str
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    quantities: tuple[Quantity, ...] = field(default_factory=tuple)

    def __getitem__(self, name: str) -> Quantity:
        for q in self.quantities:
            if q.name == name:
                return q
        raise KeyError(name)


def _need(setup: Setup, *names: str) -> None:
    missing = [n for n in names if getattr(setup, n) is None]
    if missing:
        raise ValueError(f"model {setup.model!r} needs: {', '.join(missing)}")


def build_spot(setup: Setup) -> Spot:
    """Create the beam model selected in ``setup``."""
    if setup.model not in MODELS:
        raise ValueError(f"unknown model {setup.model!r}; use one of {MODELS}")
    if setup.model == "flat_top":
        _need(setup, "flat_top_diameter")
        if setup.defocus != 0.0:
            raise ValueError("the flat_top model has no propagation; give the spot size on target")
        return FlatTopSpot(setup.flat_top_diameter)
    if setup.model == "gaussian":
        _need(setup, "wavelength", "focal_length", "beam_radius")
        return GaussianSpot(
            setup.wavelength, setup.focal_length, setup.beam_radius, setup.m2, setup.defocus
        )
    # Diffraction models: Fresnel propagation to the target, M^2 = 1 only.
    input_radius = _aperture_input_radius(setup)
    best = best_focus_distance(
        setup.wavelength, setup.focal_length, setup.aperture_radius, input_radius
    )
    distance = best + setup.defocus
    if distance <= 0.0:
        raise ValueError("the target cannot be at or behind the lens")
    return FresnelSpot(
        setup.wavelength, setup.focal_length, setup.aperture_radius, distance, input_radius
    )


def _aperture_input_radius(setup: Setup) -> float | None:
    """Check the inputs of an aperture model; return the beam radius (None: uniform)."""
    if setup.model == "airy":
        _need(setup, "wavelength", "focal_length", "aperture_radius")
        return None
    _need(setup, "wavelength", "focal_length", "beam_radius", "aperture_radius")
    if setup.m2 != 1.0:
        raise ValueError("the truncated_gaussian model supports M^2 = 1 only")
    return setup.beam_radius


def focus_geometry(setup: Setup) -> tuple[float, float, float]:
    """Best focus and Rayleigh lengths: (offset, toward the lens, away from the lens), m.

    ``offset`` is the position of best focus relative to the geometric focal plane
    (lens + f), negative toward the lens. The Rayleigh lengths are the distances
    from best focus at which the peak fluence halves (see
    :func:`beamforge.focus.aperture_rayleigh_lengths`). For the Gaussian model the
    waist lies in the focal plane by assumption and both lengths are
    z_R = pi w0^2 / (M^2 lambda) (Siegman, *Lasers*, ch. 17).
    """
    if setup.model == "flat_top":
        raise ValueError("the flat_top model has no propagation, so it has no focus")
    if setup.model == "gaussian":
        _need(setup, "wavelength", "focal_length", "beam_radius")
        spot = GaussianSpot(setup.wavelength, setup.focal_length, setup.beam_radius, setup.m2)
        return 0.0, spot.rayleigh_range, spot.rayleigh_range
    input_radius = _aperture_input_radius(setup)
    args = (setup.wavelength, setup.focal_length, setup.aperture_radius, input_radius)
    toward, away = aperture_rayleigh_lengths(*args)
    return best_focus_distance(*args) - setup.focal_length, toward, away


@dataclass(frozen=True)
class FocusScan:
    """Spot size and effective area against the target distance from best focus.

    Arrays share one index. ``distance`` is in metres from best focus, negative
    toward the lens; ``best_a_eff`` is the effective area at best focus, so the
    peak fluence relative to best focus is ``best_a_eff / a_eff``. ``centre_is_peak`` is
    False where the spot is ring-shaped: its FWHM and 1/e^2 diameters are then those
    of the brightest ring, while A_eff and the peak fluence stay well defined.
    """

    distance: np.ndarray
    fwhm: np.ndarray
    diameter_1e2: np.ndarray
    a_eff: np.ndarray
    centre_is_peak: np.ndarray
    best_a_eff: float
    best_focus_offset: float
    rayleigh_toward_lens: float
    rayleigh_away_from_lens: float

    @property
    def relative_peak_fluence(self) -> np.ndarray:
        return self.best_a_eff / self.a_eff


def through_focus(setup: Setup, points: int = 61, span: float = 2.0) -> FocusScan:
    """The spot of the selected model at distances from best focus.

    Covers ``span`` Rayleigh lengths toward the lens and ``span`` away from it, in
    ``points`` steps that include best focus. Every point is the spot of the same
    model with only the target position changed; no new physics is involved.
    """
    offset, toward, away = focus_geometry(setup)
    half = max(points // 2, 1)
    distance = np.concatenate(
        [np.linspace(-span * toward, 0.0, half + 1)[:-1], np.linspace(0.0, span * away, half + 1)]
    )
    spots = [build_spot(replace(setup, defocus=float(d))) for d in distance]
    return FocusScan(
        distance=distance,
        fwhm=np.array([s.fwhm for s in spots]),
        diameter_1e2=np.array([2.0 * s.radius_1e2 for s in spots]),
        a_eff=np.array([s.a_eff for s in spots]),
        centre_is_peak=np.array([getattr(s, "centre_is_peak", True) for s in spots]),
        best_a_eff=build_spot(replace(setup, defocus=0.0)).a_eff,
        best_focus_offset=offset,
        rayleigh_toward_lens=toward,
        rayleigh_away_from_lens=away,
    )


def transmission_to_target(setup: Setup) -> float:
    """Fraction of the measured energy that reaches the target.

    Product of the listed element transmissions, times the aperture loss
    1 - exp(-2 T^2) when the model is ``truncated_gaussian`` and the energy is
    measured before the aperture. The Gaussian and flat-top models apply no
    aperture loss. The Airy model needs the energy measured after the aperture,
    because the loss depends on the (unspecified) overfilling beam.
    """
    if setup.measured not in ("before_aperture", "after_aperture"):
        raise ValueError("measured must be 'before_aperture' or 'after_aperture'")
    total = en.total_transmission(setup.transmissions)
    if setup.measured == "before_aperture":
        if setup.model == "airy":
            raise ValueError("the airy model needs the energy measured after the aperture")
        if setup.model == "truncated_gaussian":
            total *= en.gaussian_aperture_transmission(setup.aperture_radius / setup.beam_radius)
    return total


def calculate(setup: Setup) -> Result:
    """Compute every on-target quantity the setup allows."""
    spot = build_spot(setup)
    rows: list[Quantity] = []

    def add(name, value, unit, scale, display_unit, definition):
        rows.append(Quantity(name, value, unit, scale, display_unit, definition))

    r_e2 = spot.radius_1e2
    add("spot_fwhm", spot.fwhm, "m", 1e6, "um", "full width at half maximum of intensity")
    add("spot_diameter_1e2", 2 * r_e2, "m", 1e6, "um",
        "diameter where intensity falls to exp(-2) of the peak")  # fmt: skip
    add("a_eff", spot.a_eff, "m^2", 1e12, "um^2", "effective area, integral of I/I_max")
    if isinstance(spot, GaussianSpot):
        add("waist_radius", spot.waist_radius, "m", 1e6, "um",
            "w0 = M^2 lambda f / (pi w), 1/e^2 radius at focus")  # fmt: skip
    if setup.model == "airy":
        ring = AirySpot(setup.wavelength, setup.focal_length, setup.aperture_radius)
        add("first_dark_ring_diameter", ring.first_dark_ring_diameter, "m", 1e6, "um",
            "diameter of the first zero in the focal plane, 1.22 lambda / NA")  # fmt: skip
    if setup.model != "flat_top":
        offset, toward, away = focus_geometry(setup)
        halves = "distance from best focus at which the peak fluence falls to half"
        if setup.model == "gaussian":
            halves += ", z_R = pi w0^2 / (M^2 lambda)"
        add("rayleigh_length_toward_lens", toward, "m", 1e3, "mm", halves + ", toward the lens")
        add("rayleigh_length_away_from_lens", away, "m", 1e3, "mm",
            halves + ", away from the lens")  # fmt: skip
        add("best_focus_offset", offset, "m", 1e3, "mm",
            "best focus minus focal plane (lens + f), negative = toward the lens")  # fmt: skip

    given = [
        n
        for n in ("average_power", "pulse_energy", "target_peak_fluence")
        if getattr(setup, n) is not None
    ]
    if len(given) > 1:
        raise ValueError(f"give only one of {', '.join(given)}")

    energy_on_target = None
    if given:
        trans = transmission_to_target(setup)
        add("transmission_to_target", trans, "", 1.0, "",
            "element transmissions x aperture loss (if measured before aperture)")  # fmt: skip
        if setup.target_peak_fluence is not None:
            if trans == 0.0:
                raise ValueError("the transmission to the target is zero, so no energy reaches it")
            energy_on_target = setup.target_peak_fluence * spot.a_eff
            required = energy_on_target / trans
            add("required_pulse_energy", required, "J", 1.0, "J",
                "at the measurement point, for the target peak fluence")  # fmt: skip
            if setup.rep_rate is not None:
                add("required_average_power", required * setup.rep_rate, "W", 1.0, "W",
                    "at the measurement point, E x f_rep")  # fmt: skip
        elif setup.pulse_energy is not None:
            energy_on_target = setup.pulse_energy * trans
        else:
            _need(setup, "rep_rate")
            energy_on_target = en.pulse_energy(setup.average_power, setup.rep_rate) * trans

    if energy_on_target is not None:
        add("pulse_energy_on_target", energy_on_target, "J", 1.0, "J", "after all losses")
        if setup.rep_rate is not None:
            add("average_power_on_target", energy_on_target * setup.rep_rate, "W", 1.0, "W",
                "E x f_rep")  # fmt: skip
        fl = en.fluence_definitions(energy_on_target, spot)
        j_cm2 = (1e-4, "J/cm^2")
        add("fluence_peak", fl["peak"], "J/m^2", *j_cm2, "peak fluence F0 = E / A_eff")
        add("fluence_average_fwhm_disc", fl["average_fwhm_disc"], "J/m^2", *j_cm2,
            "energy inside the FWHM-diameter disc / disc area")  # fmt: skip
        add("fluence_average_1e2_disc", fl["average_1e2_disc"], "J/m^2", *j_cm2,
            "energy inside the 1/e^2-diameter disc / disc area")  # fmt: skip
        add("fluence_gaussian_equivalent", fl["gaussian_equivalent"], "J/m^2", *j_cm2,
            "2E / (pi w^2), w = 1/e^2 radius of the actual profile")  # fmt: skip
        if setup.pulse_duration is not None:
            add("intensity_peak",
                en.peak_intensity(fl["peak"], setup.pulse_duration, setup.pulse_shape),
                "W/m^2", 1e-4, "W/cm^2",
                f"I0 = k F0 / tau, {setup.pulse_shape} pulse, tau = FWHM duration")  # fmt: skip

    if setup.scan_speed is not None:
        _need(setup, "rep_rate")
        for label, d in (("fwhm", spot.fwhm), ("1e2", 2 * r_e2)):
            add(f"pulses_per_spot_{label}",
                en.pulses_per_spot(d, setup.rep_rate, setup.scan_speed), "", 1.0, "",
                f"N = d f_rep / v, d = {label} spot diameter")  # fmt: skip
            add(f"pulse_overlap_{label}",
                en.pulse_overlap(d, setup.rep_rate, setup.scan_speed), "", 1.0, "",
                f"1 - v / (f_rep d), d = {label} spot diameter")  # fmt: skip

    truncation = None
    if setup.aperture_radius is not None and setup.beam_radius is not None:
        truncation = setup.aperture_radius / setup.beam_radius
    warnings = list(model_warnings(setup.model, truncation))
    if setup.focal_length is not None:
        pupil = setup.aperture_radius if setup.model != "gaussian" else setup.beam_radius
        if pupil is not None and pupil / setup.focal_length > 0.2:
            warnings.append(
                f"NA ~ {pupil / setup.focal_length:.2g} is high; the paraxial scalar "
                "model loses accuracy (vectorial focusing is out of scope)."
            )
    if setup.m2 != 1.0 and setup.model != "gaussian":
        warnings.append("M^2 is ignored by this model.")
    if isinstance(spot, FresnelSpot) and not spot.centre_is_peak:
        warnings.append(
            "At this target position the spot is ring-shaped (its centre is not the "
            "brightest point); the FWHM and 1/e^2 diameters are the outer edges of the "
            "brightest ring."
        )

    return Result(spot.name, tuple(spot.assumptions), tuple(warnings), tuple(rows))
