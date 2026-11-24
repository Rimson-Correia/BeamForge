# Specification

Working title: BeamForge

## 1. Scope

A calculator for laser parameters on target. The user describes the laser, the beam
and the focusing optics; the tool returns the focal spot and the energy quantities.
It works in both directions: from measured power to fluence, and from a target
fluence to the required energy and power.

Out of scope for version 1: vectorial (high-NA) focusing, lens aberrations, nonlinear
propagation, material response. Control of lab hardware is out of scope permanently.

## 2. User inputs

| Group | Inputs |
|---|---|
| Laser | wavelength, repetition rate, pulse duration and temporal shape (Gaussian, sech², rectangular) |
| Energy | average power or energy per pulse, where it is measured, transmission of each element between that point and the target |
| Beam before the lens | profile type, diameter and which definition it uses (1/e², FWHM, flat-top width), M² |
| Aperture | none, or circular with a given diameter |
| Focusing | focal length, distance of the target from best focus (negative toward the lens) |
| Scanning (optional) | scan speed, line spacing |
| Uncertainties (optional) | standard uncertainty on any input |

## 3. Beam models

| Model | When the user picks it |
|---|---|
| Ideal Gaussian | beam much smaller than every aperture |
| Gaussian with M² | real beam, no clipping |
| Truncated Gaussian | Gaussian clipped by a circular aperture, any truncation ratio |
| Uniform circular aperture (Airy) | beam heavily overfilled, flat illumination |
| Flat-top at target | imaged or shaped beam |
| Measured profile | a camera image of the spot, with pixel size and magnification |

The tool should warn when the chosen model does not fit the inputs, for example an
ideal Gaussian selected while the aperture clips the beam noticeably.

## 4. Formulas

Symbols: λ wavelength, f focal length, w input 1/e² intensity radius, a aperture
radius, T = a/w truncation ratio, E pulse energy on target, f_rep repetition rate.

**Energy**
- E = P_avg / f_rep, then multiplied by the transmission to the target.
- Fraction of a Gaussian beam passing a centred aperture: 1 − exp(−2T²).

**Fluence (the central definition)**
- Peak fluence F₀ = E / A_eff, with A_eff = ∬ I(x,y) / I_max dA.
- Also report, clearly labelled: average fluence over the FWHM disc, average over
  the 1/e² disc, and the Gaussian-equivalent value 2E/(πw₀²).

**Gaussian focus**
- w₀ = M² λ f / (π w), FWHM = w₀ √(2 ln 2), A_eff = π w₀² / 2.
- Rayleigh range z_R = π w₀² / (M² λ).

**Uniform aperture (Airy)**
- I(x)/I₀ = [2 J₁(x)/x]², x = 2π a ρ / (λ f).
- FWHM = 0.5145 λ/NA, first dark ring diameter = 1.22 λ/NA, NA ≈ a/f.
- A_eff = λ² f² / (π a²).

**Truncated Gaussian**
- Focal field: U(ρ) ∝ ∫₀ᵃ exp(−r²/w²) J₀(2π r ρ / (λ f)) r dr.
- FWHM from a numerical root of |U(ρ)/U(0)|² = 0.5.
- A_eff = λ² f² (1 − e^(−2T²)) / [2π w² (1 − e^(−T²))²].
- Limits to test: T → ∞ gives the Gaussian result, T → 0 gives the Airy result.

**Through focus (Gaussian, truncated Gaussian, Airy)**
- Field at a distance z from the lens, aperture at the lens (paraxial Fresnel
  diffraction): U(ρ, z) = (2π a² / (λ z)) ∫₀¹ A(s) exp(i ψ s²) J₀(x s) s ds, with
  s = r / a, x = 2π a ρ / (λ z), ψ = π a² (1/z − 1/f) / λ, and A(s) = exp(−T² s²)
  (truncated Gaussian) or 1 (uniform aperture). At z = f this is the focal-plane
  integral above.
- A_eff(z) = λ² z² p / (2π a² max |g|²), g the integral above, p = ∫₀¹ A(s)² s ds.
- Best focus: the plane of highest peak intensity. For a² / (λ f) ≫ 1 it lies
  slightly closer to the lens than f (focal shift). The target position is given
  as its distance from best focus, negative toward the lens.
- Rayleigh length: the distance from best focus at which the peak fluence E / A_eff
  falls to half, reported toward and away from the lens. For a Gaussian beam it is
  z_R = π w₀² / (M² λ), and the Gaussian model keeps its closed form w(z).
- Far from focus the spot can become ring-shaped. The FWHM and 1/e² diameters are
  then those of the brightest ring, and the output says so.
- References: Goodman, Introduction to Fourier Optics, ch. 4–5; Born and Wolf,
  Principles of Optics, sec. 8.8; Y. Li and E. Wolf, Opt. Commun. 39, 211 (1981).

**Flat-top:** A = π d² / 4, F = E / A.

**Measured profile:** subtract background, A_eff = Σ(I)/I_max × pixel area /
magnification². Report FWHM from a sub-pixel fit, not a pixel count.

**Intensity:** I₀ = k F₀ / τ, k = 0.94 (Gaussian), 0.88 (sech²), 1 (rectangular),
τ = FWHM pulse duration.

**Scanning:** pulses per spot N = d f_rep / v, overlap = 1 − v / (f_rep d),
with d the spot diameter in the stated definition.

**Uncertainty:** propagate input uncertainties to every output (first-order, with
a Monte Carlo option).

## 5. Validation cases

Reference setup: λ = 800 nm, f = 350 mm, input 1/e² diameter 10 mm, aperture 5 mm.

| Quantity | Expected |
|---|---|
| Airy FWHM | 57.62 µm |
| Airy first dark ring diameter | 136.6 µm |
| Truncated-Gaussian FWHM | 58.94 µm |
| Edge intensity relative to centre | 0.6065 |
| Transmitted energy fraction | 0.3935 |
| A_eff, Airy | 3993 µm² |
| A_eff, truncated Gaussian | 4014 µm² |

These values are in the geometric focal plane (z = f).

Through-focus checks:

| Case | Expected |
|---|---|
| Aperture much larger than the beam (T = 6) | Rayleigh length = Gaussian z_R (1.248 mm); best focus −f / (1 + (π w² / (λ f))²) = −4.448 µm (S. A. Self, Appl. Opt. 22, 658 (1983)) |
| Uniform aperture, a² / (λ f) ≫ 1 | focal shift −f / (1 + π² N² / 12) (Li and Wolf 1981); axial intensity [sin(u/4) / (u/4)]², u = 2π a² Δz / (λ f²) (Born and Wolf, sec. 8.8) |
| Reference setup (regression, not independent) | best focus −0.852 mm; Rayleigh length 13.19 mm toward the lens, 14.52 mm away |

These cases check the optics only. Power and pulse energy are always user inputs;
the specification fixes no values for them. Tests of the energy and fluence
functions use arbitrary round numbers chosen in the test itself.

Further checks: spot-size formulas for truncated Gaussians in H. Urey, Applied
Optics 43, 620 (2004), and Horváth and Bor, Optics Communications 222, 51 (2003).
The author also has measured FWHM values for four lenses and several beam diameters
to use as an experimental comparison.

## 6. Architecture

1. Core library: beam models, energy and fluence functions, uncertainty. No I/O.
2. Setup description: a plain file (TOML or YAML) the user can save, share and cite.
3. Command-line interface.
4. Desktop GUI built on the library, with a profile plot and a results table.
5. Export: results table (CSV) and a short report listing inputs, model,
   definitions and assumptions.

Build in that order. Release the library before starting the GUI.

## 7. Open decisions for the author

- Package name and licence (MIT or BSD-3 are usual; confirm with the supervisor
  and the institution).
- GUI toolkit.
- Target journal, which sets the documentation and history requirements.
