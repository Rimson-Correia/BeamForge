"""Read a setup description (TOML) and convert it to SI. This is the input boundary.

Every key carries its unit in its name, e.g. ``wavelength_nm``. See
``examples/reference_setup.toml`` for the full layout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from beamforge.beams import gaussian_radius_from_diameter
from beamforge.calculator import Setup

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

# (section, key) -> (Setup field, factor to SI)
_SCALARS = {
    ("laser", "wavelength_nm"): ("wavelength", 1e-9),
    ("laser", "rep_rate_hz"): ("rep_rate", 1.0),
    ("laser", "pulse_duration_fs"): ("pulse_duration", 1e-15),
    ("energy", "average_power_w"): ("average_power", 1.0),
    ("energy", "pulse_energy_j"): ("pulse_energy", 1.0),
    ("energy", "pulse_energy_uj"): ("pulse_energy", 1e-6),
    ("energy", "target_peak_fluence_j_cm2"): ("target_peak_fluence", 1e4),
    ("beam", "m2"): ("m2", 1.0),
    ("beam", "flat_top_diameter_um"): ("flat_top_diameter", 1e-6),
    ("focusing", "focal_length_mm"): ("focal_length", 1e-3),
    ("focusing", "defocus_mm"): ("defocus", 1e-3),
    ("scanning", "speed_mm_s"): ("scan_speed", 1e-3),
}
_OTHER = {
    ("laser", "pulse_shape"),
    ("energy", "measured"),
    ("energy", "transmissions"),
    ("beam", "model"),
    ("beam", "diameter_mm"),
    ("beam", "diameter_definition"),
    ("aperture", "diameter_mm"),
}


def setup_from_dict(data: dict[str, Any]) -> Setup:
    """Build a :class:`Setup` from the parsed TOML structure. Unknown keys are errors."""
    fields: dict[str, Any] = {}
    energy_keys = data.get("energy", {})
    if "pulse_energy_j" in energy_keys and "pulse_energy_uj" in energy_keys:
        raise ValueError("give only one of pulse_energy_j, pulse_energy_uj")
    for section, content in data.items():
        for key, value in content.items():
            if (section, key) in _SCALARS:
                name, factor = _SCALARS[(section, key)]
                fields[name] = float(value) * factor
            elif (section, key) not in _OTHER:
                raise ValueError(f"unknown setting [{section}] {key}")

    beam = data.get("beam", {})
    if "model" not in beam:
        raise ValueError("[beam] model is required")
    fields["model"] = beam["model"]
    if "diameter_mm" in beam:
        fields["beam_radius"] = gaussian_radius_from_diameter(
            float(beam["diameter_mm"]) * 1e-3, beam.get("diameter_definition", "1/e2")
        )
    if "diameter_mm" in data.get("aperture", {}):
        fields["aperture_radius"] = float(data["aperture"]["diameter_mm"]) * 1e-3 / 2.0
    if "pulse_shape" in data.get("laser", {}):
        fields["pulse_shape"] = data["laser"]["pulse_shape"]
    energy = data.get("energy", {})
    if "measured" in energy:
        fields["measured"] = energy["measured"]
    if "transmissions" in energy:
        fields["transmissions"] = tuple(float(t) for t in energy["transmissions"])
    return Setup(**fields)


def load_dict(path: str | Path) -> dict[str, Any]:
    """Read a TOML setup file into its plain section/key structure."""
    with open(path, "rb") as handle:
        return tomllib.load(handle)


def load_setup(path: str | Path) -> Setup:
    """Read a TOML setup file."""
    return setup_from_dict(load_dict(path))


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    return repr(value)


def dumps(data: dict[str, Any]) -> str:
    """Write the section/key structure back as TOML text (strings, numbers, lists)."""
    lines: list[str] = []
    for section, content in data.items():
        if not content:
            continue
        lines.append(f"[{section}]")
        lines += [f"{key} = {_toml_value(value)}" for key, value in content.items()]
        lines.append("")
    return "\n".join(lines)
