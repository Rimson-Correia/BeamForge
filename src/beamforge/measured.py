"""Spot parameters from a measured camera image (a 2-D array). No file I/O."""

from __future__ import annotations

import numpy as np


def effective_area_from_image(
    image, pixel_size: float, magnification: float = 1.0, background: float = 0.0
) -> float:
    """Effective area of a measured spot.

    Formula (SPEC.md section 4):
        A_eff = sum(I) / I_max * pixel_area / magnification^2
    after subtracting ``background`` from every pixel.

    ``magnification`` is image size on the camera / spot size on target.
    Assumptions: linear camera response, no saturated pixels, the whole spot is
    inside the image. I_max is the single brightest pixel, so noise biases
    A_eff low; smooth or average frames first if the image is noisy.
    """
    data = np.asarray(image, dtype=float) - background
    return float(data.sum() / data.max() * pixel_size**2 / magnification**2)


def _fwhm_1d(cut: np.ndarray) -> float:
    """Width in pixels between the linearly interpolated half-maximum crossings."""
    peak = int(np.argmax(cut))
    half = cut[peak] / 2.0

    def crossing(step: int) -> float:
        i = peak
        while cut[i] >= half:
            i += step
            if i < 0 or i >= len(cut):
                raise ValueError("profile does not fall to half maximum inside the image")
        inside = i - step  # last pixel at or above half maximum
        frac = (cut[inside] - half) / (cut[inside] - cut[i])
        return inside + step * frac

    return crossing(+1) - crossing(-1)


def fwhm_from_image(
    image, pixel_size: float, magnification: float = 1.0, background: float = 0.0
) -> tuple[float, float]:
    """FWHM of a measured spot along x and y, with sub-pixel resolution.

    Takes the row and the column through the brightest pixel and finds the
    half-maximum crossings by linear interpolation between neighbouring pixels,
    so the result is not limited to whole pixels and assumes no profile shape.
    Returns ``(fwhm_x, fwhm_y)`` in metres on target.

    Assumptions: as for :func:`effective_area_from_image`; single-peaked spot.
    """
    data = np.asarray(image, dtype=float) - background
    row, col = np.unravel_index(int(np.argmax(data)), data.shape)
    scale = pixel_size / magnification
    return _fwhm_1d(data[row, :]) * scale, _fwhm_1d(data[:, col]) * scale
