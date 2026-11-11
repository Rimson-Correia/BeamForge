"""Command-line interface: ``beamforge setup.toml [--csv results.csv]``."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import sys

from beamforge.calculator import Result, Setup, calculate
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="beamforge", description="Laser parameters on target from a setup file."
    )
    parser.add_argument("setup", help="TOML setup file")
    parser.add_argument("--csv", help="also write the results table to this CSV file")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
