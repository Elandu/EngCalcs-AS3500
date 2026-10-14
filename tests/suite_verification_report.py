"""Independent numerical cross-checks for the expanded calculation suite.

Run from the repository root with ``python tests/suite_verification_report.py``.
Expected values come from the equations or printed source examples named below;
the calculation outputs are used only as the values under test.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opencalcs_as3500.box_gutters import (  # noqa: E402
    run_box_gutter_design,
    run_rainhead_design,
)
from opencalcs_as3500.hydraulics import (  # noqa: E402
    run_channel_design,
    run_charged_pipe_system,
    run_pipe_capacity,
)
from opencalcs_as3500.roof_hydraulics import (  # noqa: E402
    run_roof_spreader,
    run_valley_gutter,
)
from opencalcs_as3500.roof_systems import (  # noqa: E402
    run_csiro_eaves_gutter,
    run_roof_catchment_plan,
)
from opencalcs_as3500.storage_routing import (  # noqa: E402
    run_detention_routing,
    run_orifice_capacity,
    run_weir_capacity,
)

G = 9.80665
NU = 1.004e-6
REPORT_PATH = ROOT / "validation" / "suite_benchmarks.json"


def _example(name: str) -> dict[str, Any]:
    record = json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))
    return record.get("inputs", record)


def _case(
    case_id: str,
    basis: str,
    inputs: dict[str, Any],
    actual: dict[str, float],
    expected: dict[str, float],
    tolerances: dict[str, float],
) -> dict[str, Any]:
    comparisons = {}
    for field, reference in expected.items():
        value = float(actual[field])
        error = abs(value - reference)
        tolerance = tolerances[field]
        comparisons[field] = {
            "actual": value,
            "expected": reference,
            "absolute_difference": error,
            "absolute_tolerance": tolerance,
            "passed": error <= tolerance,
        }
    return {
        "id": case_id,
        "source_basis_and_independent_method": basis,
        "inputs": inputs,
        "comparisons": comparisons,
        "passed": all(item["passed"] for item in comparisons.values()),
    }


def _manning_q(
    depth: float, width: float, left: float, right: float, slope: float, n: float
) -> float:
    area = depth * (width + (left + right) * depth / 2)
    perimeter = width + depth * math.sqrt(1 + left**2) + depth * math.sqrt(1 + right**2)
    return area * (area / perimeter) ** (2 / 3) * math.sqrt(slope) / n


def _normal_depth(
    flow_m3_s: float, width: float, left: float, right: float, slope: float, n: float
) -> float:
    lower, upper = 0.0, 10.0
    for _ in range(160):
        middle = (lower + upper) / 2
        if _manning_q(middle, width, left, right, slope, n) < flow_m3_s:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2


def _colebrook_factor(reynolds: float, diameter: float, roughness: float) -> float:
    """Solve Colebrook independently by bisection on Darcy friction factor."""

    def residual(factor: float) -> float:
        return 1 / math.sqrt(factor) + 2 * math.log10(
            roughness / (3.7 * diameter) + 2.51 / (reynolds * math.sqrt(factor))
        )

    lower, upper = 0.005, 0.2
    for _ in range(100):
        middle = (lower + upper) / 2
        if residual(middle) > 0:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2


def build_report() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []

    # For fixed hydraulic gradient, substitute f V^2 = 2 g D S in Colebrook
    # to solve V explicitly, then use continuity for Q and Darcy f.
    pipe = {
        "flow_lps": 1.0,
        "internal_diameter_mm": 300.0,
        "gradient": 0.003,
        "roughness_k_mm": 0.015,
        "kinematic_viscosity_m2_s": NU,
    }
    diameter = pipe["internal_diameter_mm"] / 1000
    roughness = pipe["roughness_k_mm"] / 1000
    root = math.sqrt(2 * G * diameter * pipe["gradient"])
    velocity = -2 * root * math.log10(roughness / (3.7 * diameter) + 2.51 * NU / (diameter * root))
    area = math.pi * diameter**2 / 4
    flow_lps = velocity * area * 1000
    input_velocity = pipe["flow_lps"] / 1000 / area
    reynolds = input_velocity * diameter / NU
    input_friction = _colebrook_factor(reynolds, diameter, roughness)
    pipe_result = run_pipe_capacity(pipe)["results"]
    cases.append(
        _case(
            "fixed_gradient_colebrook_pipe",
            "Colebrook with the Darcy-gradient identity substituted to solve velocity explicitly; "
            "Q=VA.",
            pipe,
            {
                key: pipe_result[key]
                for key in ("capacity_lps", "velocity_m_s", "darcy_friction_factor")
            },
            {
                "capacity_lps": flow_lps,
                "velocity_m_s": input_velocity,
                "darcy_friction_factor": input_friction,
            },
            {"capacity_lps": 1e-8, "velocity_m_s": 1e-10, "darcy_friction_factor": 1e-10},
        )
    )

    # Hagen-Poiseuille head loss for each circular laminar segment; resistances
    # add in series, with Q = delta-head / sum(R_h).
    head = 0.001
    segments = [
        {
            "id": "small",
            "length_m": 1.0,
            "internal_diameter_mm": 10.0,
            "roughness_k_mm": 0.0,
            "kinematic_viscosity_m2_s": 1e-6,
            "minor_loss_coefficients": [],
            "start_pipe_centre_level_m": 0.0,
            "end_pipe_centre_level_m": 0.0,
        },
        {
            "id": "large",
            "length_m": 2.0,
            "internal_diameter_mm": 20.0,
            "roughness_k_mm": 0.0,
            "kinematic_viscosity_m2_s": 1e-6,
            "minor_loss_coefficients": [],
            "start_pipe_centre_level_m": 0.0,
            "end_pipe_centre_level_m": 0.0,
        },
    ]
    laminar_inputs = {
        "upstream_energy_level_m": 1.0 + head,
        "downstream_energy_level_m": 1.0,
        "segments": segments,
    }
    resistance = sum(
        128
        * 1e-6
        * segment["length_m"]
        / (G * math.pi * (segment["internal_diameter_mm"] / 1000) ** 4)
        for segment in segments
    )
    laminar_flow_lps = head / resistance * 1000
    laminar_result = run_charged_pipe_system(laminar_inputs)["results"]
    cases.append(
        _case(
            "laminar_charged_series",
            "Hagen-Poiseuille resistance 128 nu L/(g pi D^4) for each segment; "
            "series resistances sum.",
            laminar_inputs,
            {
                "flow_lps": laminar_result["flow_lps"],
                "head_balance_residual_m": laminar_result["head_balance_residual_m"],
            },
            {"flow_lps": laminar_flow_lps, "head_balance_residual_m": 0.0},
            {"flow_lps": 1e-9, "head_balance_residual_m": 1e-10},
        )
    )

    # Solve the asymmetric trapezoid normal-depth equation independently by
    # bisection, using the requested 50 L/s as the target flow.
    channel = {
        "shape": "trapezoidal",
        "bottom_width_m": 0.4,
        "left_side_slope_horizontal_to_vertical": 1.0,
        "right_side_slope_horizontal_to_vertical": 2.0,
        "channel_gradient": 0.01,
        "manning_n": 0.015,
        "design_flow_lps": 50.0,
    }
    normal = _normal_depth(0.05, 0.4, 1.0, 2.0, 0.01, 0.015)
    channel_result = run_channel_design(channel)["results"]
    cases.append(
        _case(
            "asymmetric_manning_normal_depth",
            "Manning trapezoid area/perimeter with distinct left/right side slopes; "
            "bisection solves Q=50 L/s.",
            channel,
            {
                "normal_depth_m": channel_result["normal_depth_m"],
                "capacity_lps": channel_result["capacity_lps"],
            },
            {"normal_depth_m": normal, "capacity_lps": 50.0},
            {"normal_depth_m": 1e-10, "capacity_lps": 1e-8},
        )
    )

    # No-outlet runoff is exactly area * intensity / 3600 * duration / 1000.
    no_outlet = {
        "stage_storage": [
            {"stage_m": 0.0, "storage_m3": 0.0},
            {"stage_m": 1.0, "storage_m3": 100.0},
        ],
        "stage_discharge": [
            {"stage_m": 0.0, "discharge_lps": 0.0},
            {"stage_m": 1.0, "discharge_lps": 0.0},
        ],
        "hyetograph": [{"duration_s": 100.0, "rainfall_intensity_mm_per_hour": 360.0}],
        "catchment_area_m2": 1000.0,
        "runoff_coefficient": 1.0,
        "loss_rate_mm_per_hour": 0.0,
        "allowable_discharge_lps": 0.0,
        "duration_step_s": 10.0,
    }
    no_outlet_volume = 1000 * 360 / 3600 * 100 / 1000
    no_outlet_result = run_detention_routing(no_outlet)["results"]
    cases.append(
        _case(
            "storage_constant_event_no_outlet",
            "Direct event volume: Ac * R/3600 * duration / 1000; no physical outlet is supplied.",
            no_outlet,
            {
                "peak_storage_m3": no_outlet_result["peak_storage_m3"],
                "mass_balance_error_m3": no_outlet_result["mass_balance_error_m3"],
            },
            {"peak_storage_m3": no_outlet_volume, "mass_balance_error_m3": 0.0},
            {"peak_storage_m3": 1e-9, "mass_balance_error_m3": 1e-9},
        )
    )

    # Continuous linear-reservoir solution dS/dt = I-kS. The routing uses
    # trapezoidal Modified Puls, so allow the small time-discretization error.
    reservoir = {
        "tank_plan_area_m2": 10.0,
        "tank_bottom_stage_m": 0.0,
        "tank_top_stage_m": 2.0,
        "stage_discharge": [
            {"stage_m": 0.0, "discharge_lps": 0.0},
            {"stage_m": 2.0, "discharge_lps": 2.0},
        ],
        "hyetograph": [{"duration_s": 100.0, "rainfall_intensity_mm_per_hour": 3.6}],
        "catchment_area_m2": 1000.0,
        "runoff_coefficient": 1.0,
        "loss_rate_mm_per_hour": 0.0,
        "allowable_discharge_lps": 100.0,
        "duration_step_s": 1.0,
    }
    inflow_m3_s = 0.001
    reservoir_decay_s = 0.0001
    reservoir_expected = (
        inflow_m3_s / reservoir_decay_s * (1 - math.exp(-reservoir_decay_s * 100.0))
    )
    reservoir_result = run_detention_routing(reservoir)["results"]
    cases.append(
        _case(
            "storage_linear_reservoir_analytic",
            "Continuous solution S(t)=I/k*(1-exp(-k*t)); compare to 1 s trapezoidal "
            "Modified Puls routing.",
            reservoir,
            {"peak_storage_m3": reservoir_result["peak_storage_m3"]},
            {"peak_storage_m3": reservoir_expected},
            {"peak_storage_m3": 1e-6},
        )
    )

    orifice = {"opening_area_m2": 0.01, "discharge_coefficient": 0.62, "head_m": 1.0}
    orifice_expected = 1000 * 0.62 * 0.01 * math.sqrt(2 * G * 1.0)
    orifice_actual = run_orifice_capacity(orifice)["results"]["capacity_lps"]
    cases.append(
        _case(
            "free_orifice_capacity",
            "Q = Cd A sqrt(2 g H), converted from m3/s to L/s.",
            orifice,
            {"capacity_lps": orifice_actual},
            {"capacity_lps": orifice_expected},
            {"capacity_lps": 1e-10},
        )
    )

    weir = {"crest_length_m": 1.0, "discharge_coefficient": 1.7, "head_m": 0.25}
    weir_expected = 1000 * 1.7 * 1.0 * 0.25**1.5
    weir_actual = run_weir_capacity(weir)["results"]["capacity_lps"]
    cases.append(
        _case(
            "free_rectangular_weir_capacity",
            "Supplied-coefficient convention Q = C L H^(3/2), converted to L/s.",
            weir,
            {"capacity_lps": weir_actual},
            {"capacity_lps": weir_expected},
            {"capacity_lps": 1e-10},
        )
    )

    # Roof pitch and plan angle determine the valley side grades independently;
    # the flow check then uses the asymmetric trapezoid Manning geometry.
    valley = _example("roof_hydraulics_valley.json")
    left_pitch = math.radians(valley["left_roof_slope_degrees"])
    right_pitch = math.radians(valley["right_roof_slope_degrees"])
    plan_angle = math.radians(valley["plan_angle_degrees"])
    gx = math.tan(left_pitch) - math.tan(right_pitch) * math.cos(plan_angle)
    gy = -math.tan(right_pitch) * math.sin(plan_angle)
    norm = math.hypot(gx, gy)
    tangent_x, tangent_y = gx / norm, gy / norm
    left_grade = abs(math.tan(left_pitch) * tangent_x)
    right_grade = abs(
        math.tan(right_pitch)
        * (tangent_x * math.cos(plan_angle) + tangent_y * math.sin(plan_angle))
    )
    left_side, right_side = 1 / left_grade, 1 / right_grade
    depth = valley["flow_depth_m"]
    width = valley["bottom_width_m"]
    section = depth * (width + (left_side + right_side) * depth / 2)
    perimeter = width + depth * math.sqrt(1 + left_side**2) + depth * math.sqrt(1 + right_side**2)
    valley_capacity = (
        1000
        * section
        * (section / perimeter) ** (2 / 3)
        * math.sqrt(valley["channel_gradient"])
        / valley["manning_n"]
    )
    valley_actual = run_valley_gutter(valley)["results"]
    cases.append(
        _case(
            "valley_geometry_and_manning_capacity",
            "Intersecting-plane roof gradients derive each side slope; asymmetric trapezoid "
            "Manning capacity.",
            valley,
            {
                "left_side_slope_horizontal_to_vertical": valley_actual[
                    "left_side_slope_horizontal_to_vertical"
                ],
                "right_side_slope_horizontal_to_vertical": valley_actual[
                    "right_side_slope_horizontal_to_vertical"
                ],
                "capacity_lps": valley_actual["capacity_lps"],
            },
            {
                "left_side_slope_horizontal_to_vertical": left_side,
                "right_side_slope_horizontal_to_vertical": right_side,
                "capacity_lps": valley_capacity,
            },
            {
                "left_side_slope_horizontal_to_vertical": 1e-10,
                "right_side_slope_horizontal_to_vertical": 1e-10,
                "capacity_lps": 1e-9,
            },
        )
    )

    sheet = {
        "upper_plan_area_m2": 10.0,
        "lower_plan_area_m2": 20.0,
        "upper_roof_slope_degrees": 0.0,
        "lower_roof_slope_degrees": 0.0,
        "rainfall_intensity_mm_per_hour": 36.0,
        "upper_runoff_coefficient": 1.0,
        "lower_runoff_coefficient": 1.0,
        "spreader_width_m": 1.0,
        "sheet_depth_m": 0.01,
        "sheet_run_length_m": 1.0,
        "receiving_surface_slope": 0.01,
        "sheet_manning_n": 0.02,
        "spreader_drop_m": 0.0,
        "minor_loss_coefficient": 0.0,
    }
    sheet_area = 1.0 * 0.01
    sheet_radius = sheet_area / (1.0 + 2 * 0.01)
    sheet_capacity = 1000 * sheet_area * sheet_radius ** (2 / 3) * math.sqrt(0.01) / 0.02
    sheet_actual = run_roof_spreader(sheet)["results"]["sheet_capacity_lps"]
    cases.append(
        _case(
            "rectangular_roof_sheet_manning_capacity",
            "Rectangular sheet A=b*y and R=A/(b+2y), followed by Manning's equation.",
            sheet,
            {"sheet_capacity_lps": sheet_actual},
            {"sheet_capacity_lps": sheet_capacity},
            {"sheet_capacity_lps": 1e-9},
        )
    )

    # Martin (1973) Eq. (1) is imperial gallons/minute; the conversion is
    # 4.54609 L/imperial gallon divided by 60 seconds/minute.
    csiro = _example("roof_systems_csiro_eaves.json")
    area_ft2 = csiro["catchment_area_m2"] * 10.763910416709722
    rainfall_in_h = csiro["rainfall_intensity_mm_per_hour"] / 25.4
    flow_gpm = 0.0087 * area_ft2 * rainfall_in_h
    flow_lps = flow_gpm * 4.54609 / 60
    gutter_area_in2 = (0.00757 * area_ft2 * rainfall_in_h / (1 + 1.275)) ** 0.8
    csiro_result = run_csiro_eaves_gutter(csiro)["results"]
    cases.append(
        _case(
            "csiro_imperial_eaves_equations_and_conversion",
            "Martin (1973) Eqs. (1),(3), pp. 2,5-7; imperial gallons converted with 4.54609/60.",
            csiro,
            {
                "flow_load_imperial_gallons_per_minute": csiro_result[
                    "flow_load_imperial_gallons_per_minute"
                ],
                "flow_load_lps": csiro_result["flow_load_lps"],
                "required_gutter_area_in2_before_shape_adjustment": csiro_result[
                    "required_gutter_area_in2_before_shape_adjustment"
                ],
            },
            {
                "flow_load_imperial_gallons_per_minute": flow_gpm,
                "flow_load_lps": flow_lps,
                "required_gutter_area_in2_before_shape_adjustment": gutter_area_in2,
            },
            {
                "flow_load_imperial_gallons_per_minute": 1e-9,
                "flow_load_lps": 1e-10,
                "required_gutter_area_in2_before_shape_adjustment": 1e-10,
            },
        )
    )

    # Clauses 3.4.3/3.4.4: the standard's 30 degree table factor is 1.29;
    # the vertical wall adds half its 40 m2 area to the adjoining 20 m2 roof.
    roofs = {
        "catchments": [
            {
                "catchment_id": "north",
                "geometry": "single_slope_freely_exposed",
                "plan_area_m2": 100.0,
                "roof_slope_degrees": 30.0,
            },
            {
                "catchment_id": "north",
                "geometry": "vertical_wall_flat_roof",
                "plan_area_m2": 20.0,
                "vertical_area_m2": 40.0,
            },
            {
                "catchment_id": "south",
                "geometry": "adjacent_sloping_roofs",
                "plan_area_1_m2": 40.0,
                "plan_area_2_m2": 35.0,
                "vertical_area_1_m2": 18.0,
                "vertical_area_2_m2": 30.0,
            },
        ]
    }
    north_expected = 100 * 1.29 + 20 + 40 / 2
    south_expected = 40 + 35 + abs(30 - 18) / 2
    roof_result = run_roof_catchment_plan(roofs)["results"]
    grouped = {row["catchment_id"]: row["catchment_area_m2"] for row in roof_result["catchments"]}
    cases.append(
        _case(
            "roof_slope_wall_and_grouped_catchment_arithmetic",
            "Table 3.4.3.2 30 degree factor=1.29; Clause 3.4.4.1 wall term=0.5 Av; "
            "adjacent roof uses 0.5 absolute vertical-area difference.",
            roofs,
            {
                "north_catchment_area_m2": grouped["north"],
                "south_catchment_area_m2": grouped["south"],
                "total_catchment_area_m2": roof_result["total_catchment_area_m2"],
            },
            {
                "north_catchment_area_m2": north_expected,
                "south_catchment_area_m2": south_expected,
                "total_catchment_area_m2": north_expected + south_expected,
            },
            {
                "north_catchment_area_m2": 1e-10,
                "south_catchment_area_m2": 1e-10,
                "total_catchment_area_m2": 1e-10,
            },
        )
    )

    # Published Appendix I.1 geometry anchors supplement, but do not replace,
    # independent equation cases above.
    box_inputs = _example("appendix_i1_box_gutter.json")
    box_actual = run_box_gutter_design(box_inputs)["results"]
    cases.append(
        _case(
            "appendix_i1_box_gutter_chart_anchor",
            "Printed Appendix I.1 / Figure H.1 worked-example anchor: 15 L/s, 450 mm width, "
            "1:200 gradient -> 140 mm.",
            box_inputs,
            {
                "minimum_depth_including_freeboard_mm": box_actual[
                    "minimum_depth_including_freeboard_mm"
                ]
            },
            {"minimum_depth_including_freeboard_mm": 140.0},
            {"minimum_depth_including_freeboard_mm": 0.0},
        )
    )
    rainhead_inputs = _example("appendix_i1_rainhead.json")
    rainhead_actual = run_rainhead_design(rainhead_inputs)["results"]
    cases.append(
        _case(
            "appendix_i1_rainhead_geometry_anchor",
            "Appendix I.1 H.3: ceil(1.67*144 mm)=241 mm minimum depth; "
            "printed minimum length anchor=185 mm.",
            rainhead_inputs,
            {
                "minimum_total_depth_mm": rainhead_actual["minimum_total_depth_mm"],
                "minimum_length_mm": rainhead_actual["minimum_length_mm"],
            },
            {"minimum_total_depth_mm": math.ceil(1.67 * 144), "minimum_length_mm": 185.0},
            {"minimum_total_depth_mm": 0.0, "minimum_length_mm": 0.0},
        )
    )

    return {
        "report": "expanded numerical verification",
        "standard": "AS/NZS 3500.3:2025 plus explicitly identified historical CSIRO example",
        "generator": "tests/suite_verification_report.py",
        "method": (
            "Expected values are independently evaluated from named equations or printed "
            "Appendix I anchors. Runtime outputs appear only as actual values. Routing's "
            "linear-reservoir case uses an analytic continuous solution with a tolerance for "
            "Modified Puls time-step error."
        ),
        "passed": all(case["passed"] for case in cases),
        "case_count": len(cases),
        "cases": cases,
    }


if __name__ == "__main__":
    report = build_report()
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    status = "PASS" if report["passed"] else "FAIL"
    print(f"{status}: {report['case_count']} independent suites -> {REPORT_PATH}")
    raise SystemExit(0 if report["passed"] else 1)
