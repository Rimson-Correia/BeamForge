# BeamForge

Computes laser parameters on target (spot size, pulse energy, average power,
fluence, intensity) from a user-defined optical setup. The fluence is computed
from the actual focal profile of the chosen beam model, not from an assumed
flat-top or ideal Gaussian spot. Requirements are in [SPEC.md](SPEC.md).

Status: early development. BeamForge is a working name. Licence: MIT, see
[LICENSE](LICENSE).

## Install

```bash
pip install -e ".[dev]"
```

## Worked example

[examples/reference_setup.toml](examples/reference_setup.toml) describes an
800 nm beam of 10 mm 1/e² diameter, clipped by a 5 mm aperture and focused by a
350 mm lens.

```bash
beamforge examples/reference_setup.toml --csv results.csv
```

The report lists the inputs, the beam model, its assumptions, any warnings, and
every result with its definition. For this setup the spot FWHM is 58.94 µm and
A_eff is 4014 µm², compared with 20.99 µm and 499 µm² if the aperture were
ignored and an ideal Gaussian assumed.

The same from Python, in SI units:

```python
from beamforge import Setup, calculate

result = calculate(
    Setup(
        model="truncated_gaussian",
        wavelength=800e-9,
        focal_length=0.35,
        beam_radius=5e-3,  # 1/e² intensity radius before the lens
        aperture_radius=2.5e-3,
        rep_rate=1e3,
        average_power=1.0,
        measured="before_aperture",
    )
)
print(result["fluence_peak"].value)  # J/m²
```

To go from a wanted fluence to the required energy and power, give
`target_peak_fluence` (`target_peak_fluence_j_cm2` in the file) instead of a
power.

## Beam models

| `model` | Class | Needs |
|---|---|---|
| `gaussian` | `GaussianSpot` | beam diameter, focal length; optional M², defocus |
| `truncated_gaussian` | `TruncatedGaussianSpot` | beam diameter, aperture, focal length |
| `airy` | `AirySpot` | aperture, focal length |
| `flat_top` | `FlatTopSpot` | spot diameter on target |

A measured camera image is handled by `beamforge.measured`
(`effective_area_from_image`, `fwhm_from_image`); it is not yet wired into the
setup file.

## Fluence definitions

"Fluence" is never reported without its definition:

- `fluence_peak`: F₀ = E / A_eff, with A_eff = ∬ I/I_max dA. The central value.
- `fluence_average_fwhm_disc`: energy inside the FWHM-diameter disc / disc area.
- `fluence_average_1e2_disc`: energy inside the 1/e²-diameter disc / disc area.
- `fluence_gaussian_equivalent`: 2E / (π w²) with w the 1/e² radius of the
  actual profile.

## Assumptions

Scalar field, paraxial focusing, ideal thin lens. The diffraction models
(`truncated_gaussian`, `airy`) are valid in the focal plane only. Each model
lists its own assumptions in the output.

## Uncertainties

`beamforge.uncertainty` propagates standard uncertainties through any function
of named inputs, first-order (`propagate_first_order`) or by Monte Carlo
(`propagate_monte_carlo`). It is not yet wired into the setup file.

## Design decisions

These choices are not fixed by SPEC.md. The author reviewed and accepted them
on 2026-11-11:

1. Defocus is implemented for the Gaussian model only, w(z) = w₀√(1+(z/z_R)²).
   The diffraction models reject a non-zero defocus.
2. The truncated-Gaussian model accepts M² = 1 only.
3. For non-Gaussian profiles the "1/e² disc" is the disc whose radius is where
   I/I_max first falls to e⁻²; the Gaussian-equivalent fluence uses that radius.
4. Energy measured `before_aperture` is multiplied by 1 − exp(−2T²) for the
   truncated-Gaussian model only. The Airy model requires `after_aperture`.
5. Model-mismatch warnings: Gaussian model with T = a/w < 2.3 (Siegman's 4.6w
   aperture criterion); Airy model with edge intensity below 80 % of centre.
6. Measured-profile FWHM uses linearly interpolated half-maximum crossings on
   the row and column through the brightest pixel, not a model fit. I_max is
   the brightest pixel.
7. Pulse-shape factors use the exact values 0.9394 and 0.8814 rather than the
   rounded 0.94 and 0.88.
8. Line spacing (SPEC.md section 2) has no formula in SPEC.md and is not
   implemented.

## Tests

```bash
pytest
```

The tests cover the SPEC.md section 5 validation table, the T → 0 and T → ∞
limits of the truncated Gaussian, and analytic values for every other model.
