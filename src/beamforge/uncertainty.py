"""Uncertainty propagation for any function of named scalar inputs. No I/O."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping

import numpy as np

Model = Callable[..., Mapping[str, float]]


def propagate_first_order(
    func: Model,
    values: Mapping[str, float],
    sigmas: Mapping[str, float],
    rel_step: float = 1e-6,
) -> dict[str, tuple[float, float]]:
    """First-order (linear) propagation of standard uncertainties.

    Formula: u(y)^2 = sum_i (dy/dx_i)^2 u(x_i)^2, with the derivatives taken by
    central finite differences.

    Assumptions: inputs are uncorrelated and the model is close to linear over
    the range of each uncertainty.
    Reference: JCGM 100:2008 (GUM), eq. (10).

    ``func`` is called with ``values`` as keyword arguments and returns a mapping
    of output names to numbers. Returns ``{output: (value, standard uncertainty)}``.
    """
    base = func(**values)
    variance = {key: 0.0 for key in base}
    for name, sigma in sigmas.items():
        x = values[name]
        h = abs(x) * rel_step or rel_step
        up = func(**{**values, name: x + h})
        down = func(**{**values, name: x - h})
        for key in base:
            variance[key] += ((up[key] - down[key]) / (2.0 * h) * sigma) ** 2
    return {key: (base[key], math.sqrt(variance[key])) for key in base}


def propagate_monte_carlo(
    func: Model,
    values: Mapping[str, float],
    sigmas: Mapping[str, float],
    samples: int = 2000,
    seed: int | None = None,
) -> dict[str, tuple[float, float]]:
    """Monte Carlo propagation of standard uncertainties.

    Each uncertain input is drawn from a normal distribution N(value, sigma);
    the result is the sample mean and sample standard deviation of each output.

    Assumptions: inputs are uncorrelated and normally distributed.
    Reference: JCGM 101:2008 (GUM Supplement 1).
    """
    rng = np.random.default_rng(seed)
    draws = {name: rng.normal(values[name], sigma, samples) for name, sigma in sigmas.items()}
    outputs: dict[str, list[float]] = {}
    for i in range(samples):
        result = func(**{**values, **{name: float(d[i]) for name, d in draws.items()}})
        for key, value in result.items():
            outputs.setdefault(key, []).append(value)
    return {
        key: (float(np.mean(vals)), float(np.std(vals, ddof=1))) for key, vals in outputs.items()
    }
