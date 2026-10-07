"""Independent arithmetic comparisons for selected AS/NZS 3500.3 calculations."""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from opencalcs_as3500 import __version__
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
    flat_roof_inputs = {
        "plan_area_m2": 240,
        "roof_slope_degrees": 0,
        "wind_exposure": "freely_exposed",
    }
    roof_inputs = _example("roof_catchment.json")
    roof_angle = math.radians(roof_inputs["roof_slope_degrees"])
    roof_area_expected = roof_inputs["plan_area_m2"] * (1 + 0.5 * math.tan(roof_angle))

    roof_flow_inputs = _example("roof_flow.json")
    roof_flow_expected = (
        roof_flow_inputs["catchment_area_m2"]
        * roof_flow_inputs["design_rainfall_intensity_mm_per_hour"]
        / 3600
    )

    pervious_base_inputs = _example("pervious_runoff_coefficient.json")
    base_coefficient = 0.0133 * pervious_base_inputs["rainfall_10yr_60min_mm_per_hour"] - 0.233
    clay_inputs = {
        "rainfall_10yr_60min_mm_per_hour": 44.4,
        "runoff_coefficient_multiplier_m": 0.85,
        "soil_type": "clay",
    }
    sand_inputs = {
        "rainfall_10yr_60min_mm_per_hour": 44.4,
        "runoff_coefficient_multiplier_m": 1.05,
        "soil_type": "sand",
    }

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

    trapezoid_inputs = {
        "shape": "trapezoidal",
        "bottom_width_m": 0.4,
        "flow_depth_m": 0.2,
        "side_slope_horizontal_to_vertical": 1,
        "channel_gradient": 0.01,
        "manning_n": 0.013,
    }
    trapezoid_area = trapezoid_inputs["flow_depth_m"] * (
        trapezoid_inputs["bottom_width_m"]
        + trapezoid_inputs["side_slope_horizontal_to_vertical"] * trapezoid_inputs["flow_depth_m"]
    )
    trapezoid_perimeter = trapezoid_inputs["bottom_width_m"] + 2 * trapezoid_inputs[
        "flow_depth_m"
    ] * math.sqrt(1 + trapezoid_inputs["side_slope_horizontal_to_vertical"] ** 2)
    trapezoid_expected = (
        1000
        * trapezoid_area
        * (trapezoid_area / trapezoid_perimeter) ** (2 / 3)
        * math.sqrt(trapezoid_inputs["channel_gradient"])
        / trapezoid_inputs["manning_n"]
    )

    expected = [
        (
            "Flat roof catchment area",
            "Clause 3.4.3.1 plan area, including any contributing gutters.",
            run_roof_catchment(flat_roof_inputs)["results"]["catchment_area_m2"],
            flat_roof_inputs["plan_area_m2"],
        ),
        (
            "Single-slope eaves roof catchment",
            "Independent trigonometric evaluation of the stated area-factor equation.",
            run_roof_catchment(roof_inputs)["results"]["catchment_area_m2"],
            roof_area_expected,
        ),
        (
            "Australian roofed-area design flow",
            "Clause 5.4.6 coefficient 1.0 x area x intensity / 3600.",
            run_roof_flow(roof_flow_inputs)["results"]["design_flow_lps"],
            roof_flow_expected,
        ),
        (
            "Pervious runoff coefficient",
            "1.0 x (0.0133 x 44.4 - 0.233), with no soil adjustment.",
            run_pervious_coefficient(_example("pervious_runoff_coefficient.json"))["results"][
                "runoff_coefficient"
            ],
            base_coefficient,
        ),
        (
            "Pervious runoff coefficient with clay adjustment",
            "Table 5.4.6(A) multiplier 0.85, then add 0.1 for clay soil.",
            run_pervious_coefficient(clay_inputs)["results"]["runoff_coefficient"],
            0.85 * base_coefficient + 0.1,
        ),
        (
            "Pervious runoff coefficient with sandy-soil adjustment",
            "Table 5.4.6(A) multiplier 1.05, then subtract 0.1 with a 0.1 floor.",
            run_pervious_coefficient(sand_inputs)["results"]["runoff_coefficient"],
            max(0.1, 1.05 * base_coefficient - 0.1),
        ),
        (
            "Roof, impervious, and pervious surface design flow",
            "Clause 5.4.8 area-weighted sum using Australian coefficients 1.0 and 0.9 and Cp.",
            run_design_flow(_example("surface_design_flow.json"))["results"]["design_flow_lps"],
            (400 * 1.0 + 600 * 0.9 + 500 * base_coefficient) * 180 / 3600,
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
            "Trapezoidal Manning channel capacity",
            "Trapezoid area and wetted perimeter evaluated independently, then Manning capacity.",
            run_open_channel_capacity(trapezoid_inputs)["results"]["capacity_lps"],
            trapezoid_expected,
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
        "package_version": __version__,
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
