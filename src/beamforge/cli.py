"""Command-line interface: ``beamforge setup.toml [--csv f.csv] [--through-focus f.csv]``."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import sys

from beamforge.calculator import FocusScan, Result, Setup, calculate, through_focus
from beamforge.setup_file import load_setup


def format_report(setup: Setup, result: Result) -> str:
    """Plain-text report: inputs, model, assumptions, warnings, labelled results."""
    lines = [f"Beam model: {result.model}", "", "Inputs (SI units):"]
    for f in dataclasses.fields(setup):
        value = getattr(setup, f.name)
        if value is not None and value != ():
            lines.append(f"  {f.name} = {value}")
    lines += ["", "Assumptions:"] + [f"  - {a}" for a in result.assumptions]
    if result.warnings:
        lines += ["", "WARNINGS:"] + [f"  ! {w}" for w in result.warnings]
    lines += ["", "Results:"]
    width = max(len(q.name) for q in result.quantities)
    for q in result.quantities:
        lines.append(
            f"  {q.name:<{width}}  {q.display_value:>11.5g} {q.display_unit:<7} {q.definition}"
        )
    return "\n".join(lines)


def write_csv(path: str, result: Result) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["quantity", "value", "unit", "value_si", "unit_si", "definition"])
        for q in result.quantities:
            writer.writerow(
                [q.name, repr(q.display_value), q.display_unit, repr(q.value), q.unit, q.definition]
            )


def write_focus_csv(path: str, scan: FocusScan, energy: float | None = None) -> None:
    """Through-focus table: one row per target distance from best focus.

    With the pulse energy on target, the absolute peak fluence E / A_eff is added.
    """
    header = [
        "distance_from_best_focus_mm",
        "spot_fwhm_um",
        "spot_diameter_1e2_um",
        "a_eff_um2",
        "peak_fluence_relative_to_best_focus",
        "spot_centre_is_brightest",
    ]
    if energy is not None:
        header.append("peak_fluence_j_cm2")
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for i, distance in enumerate(scan.distance):
            row = [
                distance * 1e3,
                scan.fwhm[i] * 1e6,
                scan.diameter_1e2[i] * 1e6,
                scan.a_eff[i] * 1e12,
                scan.relative_peak_fluence[i],
                int(scan.centre_is_peak[i]),
            ]
            if energy is not None:
                row.append(energy / scan.a_eff[i] * 1e-4)
            writer.writerow([f"{value:.6g}" for value in row])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="beamforge", description="Laser parameters on target from a setup file."
    )
    parser.add_argument("setup", help="TOML setup file")
    parser.add_argument("--csv", help="also write the results table to this CSV file")
    parser.add_argument(
        "--through-focus",
        metavar="CSV",
        help="also write spot size and peak fluence against distance from best focus",
    )
    parser.add_argument(
        "--focus-range",
        nargs=2,
        type=float,
        metavar=("FROM_MM", "TO_MM"),
        help="range of --through-focus in mm from best focus (default: 2 Rayleigh lengths)",
    )
    args = parser.parse_args(argv)
    try:
        setup = load_setup(args.setup)
        result = calculate(setup)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(format_report(setup, result))
    if args.csv:
        write_csv(args.csv, result)
    if args.through_focus:
        try:
            limits = [v * 1e-3 for v in args.focus_range] if args.focus_range else [None, None]
            scan = through_focus(setup, start=limits[0], stop=limits[1])
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        names = {q.name: q.value for q in result.quantities}
        write_focus_csv(args.through_focus, scan, names.get("pulse_energy_on_target"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
