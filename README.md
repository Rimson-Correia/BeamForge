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
every result with its definition. Results are given at best focus, which for this
setup lies 0.85 mm closer to the lens than the focal plane: spot FWHM 58.80 µm,
A_eff 4004 µm² (58.94 µm and 4014 µm² in the focal plane itself), compared with
20.99 µm and 499 µm² if the aperture were ignored and an ideal Gaussian assumed.

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

## Depth of focus

Every model except the flat-top also reports the Rayleigh length: the distance
from best focus at which the peak fluence has fallen to half, toward the lens and
away from it. For a Gaussian beam this is z_R = π w₀² / (M² λ). For a clipped beam
the spot is computed in any plane behind the lens from the paraxial Fresnel
integral, so the two directions can differ and best focus lies slightly closer to
the lens than the focal plane.

For the reference setup: best focus 0.85 mm before the focal plane, Rayleigh
length 13.19 mm toward the lens and 14.52 mm away, a depth of focus of 27.7 mm.
The ideal-Gaussian formula, which ignores the aperture, would give 1.25 mm.

Put the target anywhere with `defocus_mm` in `[focusing]` (distance from best
focus, negative toward the lens); every result is then computed there. A table of
spot size and peak fluence against distance:

```bash
beamforge examples/reference_setup.toml --through-focus through_focus.csv
```

The table covers two Rayleigh lengths on each side of best focus; `--focus-range -50 50`
sets any other range, in mm from best focus.

In the desktop application, **Depth of focus** opens a separate window with the
same table, plots of spot diameter and peak fluence against distance, and CSV
export. Its range is automatic or typed in, and is remembered between sessions. Far from focus a clipped beam breaks into rings; the FWHM and 1/e²
diameters then jump, and where the centre is no longer the brightest point the
table and plots mark the spot as ring-shaped.

## Desktop application

![BeamForge main window](docs/screenshot.png)

The desktop application shows the inputs, the focal profile (linear or
logarithmic, and as a 2-D spot), the headline numbers and the full results table
with definitions, assumptions and warnings. Results update as you type. Setups
can be opened and saved as the same TOML files the command line uses, and
results exported as CSV or as a text report. A short start-up screen is shown
first; `--no-splash` skips it.

Run it from source:

```bash
pip install -e ".[gui]"
```

```bash
beamforge-gui examples/reference_setup.toml
```

Build a standalone `dist\BeamForge.exe` for Windows (no Python needed to run it):

```bash
pip install -e ".[gui,build]"
```

```bash
powershell -ExecutionPolicy Bypass -File packaging\build_exe.ps1
```

The interface contains no physics. It builds the same input structure as a setup
file and calls the library, so the GUI, the command line and Python give
identical numbers. It uses PySide6 (Qt) and pyqtgraph, which are optional
dependencies; the library itself needs only numpy and scipy.

## Beam models

| `model` | Class | Needs |
|---|---|---|
| `gaussian` | `GaussianSpot` | beam diameter, focal length; optional M², target distance |
| `truncated_gaussian` | `FresnelSpot` | beam diameter, aperture, focal length; optional target distance |
| `airy` | `FresnelSpot` | aperture, focal length; optional target distance |
| `flat_top` | `FlatTopSpot` | spot diameter on target |

`TruncatedGaussianSpot` and `AirySpot` are the focal-plane special cases of
`FresnelSpot` and carry the validation values of SPEC.md section 5.

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

Scalar field, paraxial focusing and propagation, ideal thin lens. The Gaussian
model places the waist in the focal plane. Each model lists its own assumptions
in the output.

## Uncertainties

`beamforge.uncertainty` propagates standard uncertainties through any function
of named inputs, first-order (`propagate_first_order`) or by Monte Carlo
(`propagate_monte_carlo`). It is not yet wired into the setup file.



## Tests

```bash
pytest
```

The tests cover the SPEC.md section 5 validation table, the T → 0 and T → ∞
limits of the truncated Gaussian, and analytic values for every other model.

## Use of AI

Parts of this code, its tests and its documentation were generated with an AI
coding tool and reviewed by the author, who is responsible for the content.
[AI_USAGE.md](AI_USAGE.md) logs what was generated and with which tool.
