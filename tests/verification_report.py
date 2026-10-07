"""Independent arithmetic comparisons for selected AS/NZS 3500.3 calculations."""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from opencalcs_as3500.calculations import (
    run_design_flow,
    run_open_channel_capacity,
    run_pervious_coefficient,
    run_roof_catchment,
    run_roof_flow,
    run_sag_pit_capacity,
)

ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = 1e-9


def _example(filename: str) -> dict:
    return json.loads((ROOT / "examples" / filename).read_text(encoding="utf-8"))


def build_report() -> dict:
    roof_inputs = _example("roof_catchment.json")
    roof_angle = math.radians(roof_inputs["roof_slope_degrees"])
    roof_area_expected = roof_inputs["plan_area_m2"] * (1 + 0.5 * math.tan(roof_angle))

    channel_inputs = _example("open_channel_capacity.json")
    channel_area = channel_inputs["bottom_width_m"] * channel_inputs["flow_depth_m"]
    channel_perimeter = channel_inputs["bottom_width_m"] + 2 * channel_inputs["flow_depth_m"]
    channel_radius = channel_area / channel_perimeter
    channel_expected = (
        1000
        * channel_area
        * channel_radius ** (2 / 3)
        * math.sqrt(channel_inputs["channel_gradient"])
        / channel_inputs["manning_n"]
    )

    expected = [
        (
            "Single-slope eaves roof catchment",
            "Independent trigonometric evaluation of the stated area-factor equation.",
            run_roof_catchment(roof_inputs)["results"]["catchment_area_m2"],
            roof_area_expected,
        ),
        (
            "Steel roof design flow",
            "0.9 x area x intensity / 3600, with L/s and SI input units.",
            run_roof_flow(_example("roof_flow.json"))["results"]["design_flow_lps"],
            0.9 * 1000 * 180 / 3600,
        ),
        (
            "Pervious runoff coefficient",
            "1.0 x (0.0133 x 44.4 - 0.233), with no soil adjustment.",
            run_pervious_coefficient(_example("pervious_runoff_coefficient.json"))["results"][
                "runoff_coefficient"
            ],
            0.0133 * 44.4 - 0.233,
        ),
        (
            "Mixed surface design flow",
            "Sum of area-weighted coefficients multiplied by intensity / 3600.",
            run_design_flow(_example("surface_design_flow.json"))["results"]["design_flow_lps"],
            (400 * 0.9 + 600 * 0.85 + 500 * 0.35752) * 180 / 3600,
        ),
        (
            "Rectangular Manning channel capacity",
            "Rectangular area and wetted perimeter evaluated independently in SI units.",
            run_open_channel_capacity(_example("open_channel_capacity.json"))["results"][
                "capacity_lps"
            ],
            channel_expected,
        ),
        (
            "Sag-pit inlet capacity",
            "1600 x blockage factor x free perimeter x ponding depth to power 1.5.",
            run_sag_pit_capacity(_example("sag_pit_capacity.json"))["results"]["capacity_lps"],
            1600 * 0.5 * 4 * 0.1**1.5,
        ),
    ]
    cases = []
    for name, source_basis, actual, reference in expected:
        difference = abs(actual - reference)
        cases.append(
            {
                "name": name,
                "source_basis": source_basis,
                "actual": actual,
                "expected": reference,
                "absolute_tolerance": TOLERANCE,
                "absolute_difference": difference,
                "passed": difference <= TOLERANCE,
            }
        )
    return {
        "package_version": "0.1.0",
        "standard": "AS/NZS 3500.3:2025",
        "method": (
            "Independent arithmetic expressions compared with calculation outputs. "
            "The published Appendix K example is recorded separately."
        ),
        "passed": all(case["passed"] for case in cases),
        "cases": cases,
    }


if __name__ == "__main__":
    report = build_report()
    path = ROOT / "validation" / "benchmarks.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    status = "PASS" if report["passed"] else "FAIL"
    print(f"{status}: {len(report['cases'])} independent calculations -> {path}")
