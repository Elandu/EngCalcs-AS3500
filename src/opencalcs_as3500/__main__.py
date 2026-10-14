# SPDX-License-Identifier: LicenseRef-EngCalcs-Proprietary
"""Command-line calculation execution and report export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from opencalcs_as3500.plugin import get_plugin


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenCalcs AS3500 drainage calculations")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List calculation descriptors as JSON")
    run = commands.add_parser("run", help="Execute a calculation from JSON")
    run.add_argument("calculation")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path)
    report = commands.add_parser("report", help="Export a freshly executed calculation pack")
    report.add_argument("--input", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    report.add_argument("--format", choices=("html", "pdf", "json"), default="html")
    args = parser.parse_args()
    plugin = get_plugin()
    try:
        if args.command == "list":
            print(json.dumps(plugin.descriptor(), indent=2))
            return
        raw = json.loads(args.input.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict):
            raise ValueError("Input JSON must be an object or calculation/input wrapper")
        expected_id = (
            args.calculation if args.command == "run" else "stormwater.as3500.calculation_pack"
        )
        if "calculation" in raw and raw["calculation"] != expected_id:
            raise ValueError("Example calculation ID does not match the requested calculation")
        inputs = raw.get("inputs", raw)
        if not isinstance(inputs, dict):
            raise ValueError("Calculation inputs must be a JSON object")
        calculations = {c.id: c for c in plugin.calculations}
        if args.command == "report":
            from opencalcs_as3500.reporting import run_calculation_pack, write_pdf

            if args.format == "pdf":
                write_pdf(inputs, args.output)
                return
            result = run_calculation_pack(inputs)
            output = (
                result["results"]["html"] if args.format == "html" else json.dumps(result, indent=2)
            )
        else:
            if args.calculation not in calculations:
                raise ValueError(f"Unknown calculation: {args.calculation}")
            output = json.dumps(
                calculations[args.calculation].run(inputs), indent=2, allow_nan=False
            )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output)
    except (ValueError, KeyError, OSError, ImportError) as exc:
        parser.exit(2, f"Calculation failed: {exc}\n")


if __name__ == "__main__":
    main()
