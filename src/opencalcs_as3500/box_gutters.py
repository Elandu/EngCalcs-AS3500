# SPDX-License-Identifier: LicenseRef-EngCalcs-Proprietary
"""Appendix H design procedures with explicit, traceable chart readings.

Chart data are supplied by a licensed designer or a manufacturer.  This module
does not substitute an unverified fitted law for the standard's design graphs.
"""

from __future__ import annotations

from math import ceil, isclose, pi, sqrt
from typing import Any

from opencalcs_as3500.appendix_h_overflow_readings import lookup_overflow_reading
from opencalcs_as3500.appendix_h_roof_readings import lookup_roof_reading
from opencalcs_as3500.calculations import _result, _validated
from opencalcs_as3500.hydraulics import run_channel_design

POS = {"type": "number", "exclusiveMinimum": 0}
NONNEG = {"type": "number", "minimum": 0}
LPS_PER_IMPERIAL_GPM = 4.54609 / 60
CHART = {
    "type": "object",
    "additionalProperties": False,
    "required": ["source", "figure", "context", "points"],
    "properties": {
        "source": {"type": "string", "minLength": 1},
        "figure": {"type": "string", "minLength": 1},
        "context": {
            "type": "object",
            "additionalProperties": {"type": ["number", "string"]},
        },
        "points": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "array",
                "minItems": 2,
                "maxItems": 2,
                "prefixItems": [NONNEG, NONNEG],
                "items": False,
            },
        },
        "interpolation": {"enum": ["linear", "upper_bracket"]},
    },
}
PIPE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["shape"],
    "properties": {
        "shape": {"enum": ["circular", "rectangular"]},
        "diameter_mm": POS,
        "width_mm": POS,
        "height_mm": POS,
    },
    "allOf": [
        {
            "if": {"properties": {"shape": {"const": "circular"}}},
            "then": {"required": ["diameter_mm"]},
        },
        {
            "if": {"properties": {"shape": {"const": "rectangular"}}},
            "then": {"required": ["width_mm", "height_mm"]},
        },
    ],
}


def _schema(required: list[str], properties: dict) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


_COMMON = {
    "design_flow_lps": POS,
    "box_width_mm": POS,
    "gradient": POS,
    "domestic_construction": {"type": "boolean"},
}
BOX_GUTTER_SCHEMA = _schema(
    ["design_flow_lps", "box_width_mm", "gradient"],
    {**_COMMON, "gutter_depth_chart": CHART, "available_depth_mm": POS},
)
BOX_HYDRAULICS_SCHEMA = _schema(
    ["design_flow_lps", "box_width_mm", "gradient", "manning_n"],
    {
        **_COMMON,
        "manning_n": POS,
        "freeboard_mm": {"type": "number", "minimum": 30},
        "available_depth_mm": POS,
    },
)
RAINHEAD_SCHEMA = _schema(
    [
        "design_flow_lps",
        "box_width_mm",
        "gradient",
        "pipe",
        "gutter_depth_at_1_in_200_mm",
    ],
    {
        **_COMMON,
        "pipe": PIPE,
        "gutter_depth_at_1_in_200_mm": POS,
        "water_depth_chart": CHART,
        "length_chart": CHART,
        "selected_depth_mm": POS,
        "selected_length_mm": POS,
        "pipe_edge_clearance_mm": NONNEG,
    },
)
_SUMP_COMMON = {
    "gutter_flows_lps": {"type": "array", "minItems": 1, "items": POS},
    "direct_roof_flow_lps": NONNEG,
    "box_width_mm": POS,
    "gradient": POS,
    "domestic_construction": {"type": "boolean"},
    "pipe": PIPE,
    "sump_depth_chart": CHART,
    "offset_chart": CHART,
}
SIDE_OVERFLOW_SCHEMA = _schema(
    [
        "gutter_flows_lps",
        "box_width_mm",
        "gradient",
        "pipe",
        "overflow_width_mm",
    ],
    {
        **_SUMP_COMMON,
        "overflow_width_mm": POS,
        "overflow_depth_chart": CHART,
        "overflow_duct_length_mm": NONNEG,
    },
)
HIGH_OVERFLOW_SCHEMA = _schema(
    [
        "gutter_flows_lps",
        "box_width_mm",
        "gradient",
        "pipe",
        "free_discharge_gutter_depth_mm",
    ],
    {**_SUMP_COMMON, "height_chart": CHART, "free_discharge_gutter_depth_mm": POS},
)


def _chart(curve: dict, x: float, figure: str, context: dict[str, float | str]) -> float:
    if curve["figure"] != figure:
        raise ValueError(f"Expected {figure} chart, received {curve['figure']}")
    for name, expected in context.items():
        if curve["context"].get(name) != expected:
            raise ValueError(f"{figure} chart context must specify {name}={expected}")
    points = [(float(a), float(b)) for a, b in curve["points"]]
    if any(b[0] <= a[0] or b[1] < a[1] for a, b in zip(points, points[1:], strict=False)):
        raise ValueError("Chart abscissae must strictly increase and ordinates must not decrease")
    if x < points[0][0] or x > points[-1][0]:
        raise ValueError(f"{figure}: extrapolation outside supplied chart range is prohibited")
    for px, py in points:
        if x == px:
            return py
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        if x0 < x < x1:
            if curve.get("interpolation", "upper_bracket") == "upper_bracket":
                return y1
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    raise ValueError("No chart segment contains the requested value")


_APPENDIX_I_CHART_ANCHORS = (
    ("H.1", {"box_width_mm": 450.0, "gradient": 0.005}, 15.0, 140.0),
    ("H.1", {"box_width_mm": 600.0, "gradient": 0.005}, 6.5, 98.0),
    ("H.1", {"box_width_mm": 600.0, "gradient": 0.005}, 8.5, 105.0),
    ("H.3.water_depth", {"pipe_family": "rectangular:150x100"}, 15.0, 144.0),
    ("H.3.length", {"gutter_depth_at_1_in_200_mm": 140.0}, 250.0, 185.0),
    ("H.4", {"pipe_family": "circular:150"}, 16.0, 220.0),
    ("H.6a", {"box_width_mm": 600.0}, 8.0, 26.0),
    ("H.6a", {"box_width_mm": 600.0}, 8.5, 27.0),
    ("H.6b", {"overflow_width_mm": 300.0}, 16.0, 132.0),
    ("H.6b", {"overflow_width_mm": 450.0}, 16.0, 102.0),
    ("H.8", {"box_width_mm": 600.0}, 8.5, 83.0),
)


def _chart_or_appendix_i(
    curve: dict | None, x: float, figure: str, context: dict[str, float | str]
) -> tuple[float, str]:
    if curve is not None:
        return _chart(curve, x, figure, context), curve["source"]
    for anchor_figure, anchor_context, anchor_x, value in _APPENDIX_I_CHART_ANCHORS:
        if anchor_figure != figure or not isclose(anchor_x, x, rel_tol=0, abs_tol=1e-9):
            continue
        if all(context.get(name) == expected for name, expected in anchor_context.items()):
            return value, "AS/NZS 3500.3:2025 Appendix I worked-example chart reading"
    reading = lookup_overflow_reading(figure, x, context)
    if reading is not None:
        return reading
    raise ValueError(
        f"{figure}: no built-in Appendix I example anchor matches; supply a sourced chart reading"
    )


def _appendix_i_upper_bracket(
    curve: dict | None, x: float, figure: str, context: dict[str, float | str]
) -> tuple[float, str]:
    """Use a worked-example ordinate as a conservative upper bracket when applicable."""
    if curve is not None:
        return _chart(curve, x, figure, context), curve["source"]
    minimum_x = 80.0 if figure == "H.3.length" else 3.0
    if x < minimum_x:
        raise ValueError(
            f"{figure}: input {x:g} is below the confirmed graph range starting at {minimum_x:g}"
        )
    candidates = [
        (anchor_x, value)
        for anchor_figure, anchor_context, anchor_x, value in _APPENDIX_I_CHART_ANCHORS
        if anchor_figure == figure
        and all(context.get(name) == expected for name, expected in anchor_context.items())
        and anchor_x >= x
    ]
    if candidates:
        anchor_x, value = min(candidates, key=lambda item: item[0])
        method = (
            "exact worked-example point"
            if isclose(anchor_x, x, rel_tol=0, abs_tol=1e-9)
            else "upper bracket"
        )
        return (
            value,
            "AS/NZS 3500.3:2025 Appendix I worked-example chart reading "
            f"({method} at {anchor_x:g})",
        )
    reading = lookup_roof_reading(figure, x, context)
    if reading is not None:
        return reading
    raise ValueError(
        f"{figure}: no supported upper-bracket reading matches; supply a sourced chart reading"
    )


def _limits(data: dict, flow: float) -> None:
    if flow > 16:
        raise ValueError("Appendix H procedure requires total outlet flow no greater than 16 L/s")
    if not 1 / 200 <= float(data["gradient"]) <= 1 / 40:
        raise ValueError("Clause 3.7.3 requires box gutter gradient between 1:200 and 1:40")
    minimum = 200 if data.get("domestic_construction", False) else 300
    if float(data["box_width_mm"]) < minimum:
        raise ValueError(
            f"Box gutter sole width must be at least {minimum} mm for this construction"
        )


def _pipe(pipe: dict) -> tuple[float, float]:
    if pipe["shape"] == "circular":
        diameter = float(pipe["diameter_mm"])
        if diameter < 90:
            raise ValueError("Clause 3.7.8 requires circular downpipes at least 90 mm")
        return pi * diameter**2 / 4, diameter
    width, height = float(pipe["width_mm"]), float(pipe["height_mm"])
    if min(width, height) < 50 or max(width, height) < 100:
        raise ValueError("Clause 3.7.8 requires rectangular downpipes at least 100 x 50 mm")
    return width * height, sqrt(4 * width * height / pi)


def _pipe_family(pipe: dict) -> str:
    if pipe["shape"] == "circular":
        return f"circular:{float(pipe['diameter_mm']):g}"
    return f"rectangular:{float(pipe['width_mm']):g}x{float(pipe['height_mm']):g}"


def run_box_gutter_design(inputs: dict[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, BOX_GUTTER_SCHEMA)
    q, width, gradient = (float(d[k]) for k in ("design_flow_lps", "box_width_mm", "gradient"))
    _limits(d, q)
    chart_depth, chart_source = _appendix_i_upper_bracket(
        d.get("gutter_depth_chart"),
        q,
        "H.1",
        {"box_width_mm": width, "gradient": gradient},
    )
    depth = ceil(chart_depth)
    return _result(
        "stormwater.as3500.box_gutter_design",
        ("3.7.2", "3.7.3", "H.1"),
        {
            "design_flow_lps": q,
            "box_width_mm": width,
            "gradient": gradient,
            "minimum_depth_including_freeboard_mm": depth,
            "required_freeboard_mm": 30,
            "available_depth_sufficient": (
                None if "available_depth_mm" not in d else d["available_depth_mm"] >= depth
            ),
            "chart_source": chart_source,
            "chart_interpolation": (
                d["gutter_depth_chart"].get("interpolation", "upper_bracket")
                if "gutter_depth_chart" in d
                else (
                    "upper_bracket_appendix_i_example"
                    if "upper bracket" in chart_source
                    else "conservative_chart_envelope"
                    if "envelope" in chart_source
                    else "exact_appendix_i_anchor"
                )
            ),
            "chart_values_supplied_by_designer": "gutter_depth_chart" in d,
        },
    )


def run_box_gutter_hydraulics(inputs: dict[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, BOX_HYDRAULICS_SCHEMA)
    q, width, gradient = (float(d[k]) for k in ("design_flow_lps", "box_width_mm", "gradient"))
    state = run_channel_design(
        {
            "shape": "rectangular",
            "bottom_width_m": width / 1000,
            "design_flow_lps": q,
            "channel_gradient": gradient,
            "manning_n": d["manning_n"],
        }
    )["results"]
    normal = state["normal_depth_m"] * 1000
    critical = 1000 * ((q / 1000 / (width / 1000)) ** 2 / 9.80665) ** (1 / 3)
    estimate = ceil(max(normal, critical) + float(d.get("freeboard_mm", 30)))
    return _result(
        "stormwater.as3500.box_gutter_hydraulics",
        ("5.4.9",),
        {
            "design_flow_lps": q,
            "normal_depth_mm": normal,
            "critical_depth_mm": critical,
            "hydraulic_depth_plus_freeboard_mm": estimate,
            "appendix_h_design_depth_evaluated": False,
            "method": "Manning uniform-flow and critical-depth diagnostic; not Figure H.1 sizing",
            "available_depth_sufficient_for_diagnostic": (
                None if "available_depth_mm" not in d else d["available_depth_mm"] >= estimate
            ),
        },
    )


CSIRO_BOX_SCHEMA = _schema(
    ["plan_catchment_area_m2", "rainfall_intensity_mm_per_hour", "water_width_mm"],
    {
        "plan_catchment_area_m2": POS,
        "rainfall_intensity_mm_per_hour": POS,
        "water_width_mm": POS,
        "sloping_area_factor": POS,
    },
)
CSIRO_RAINHEAD_SCHEMA = _schema(
    ["design_flow_lps", "downpipe_diameter_mm"],
    {"design_flow_lps": POS, "downpipe_diameter_mm": POS, "box_side_clearance_mm": NONNEG},
)


def run_csiro_box_gutter(inputs: dict[str, Any]) -> dict[str, Any]:
    """Historical chart-free box/valley gutter method from Martin (1973), Eqs 4-6."""
    d = _validated(inputs, CSIRO_BOX_SCHEMA)
    plan_ft2 = float(d["plan_catchment_area_m2"]) * 10.76391041671
    area_factor = float(d.get("sloping_area_factor", 1.0))
    catchment_ft2 = plan_ft2 * area_factor
    rainfall_in_hr = float(d["rainfall_intensity_mm_per_hour"]) / 25.4
    width_in = float(d["water_width_mm"]) / 25.4
    # Martin Eq. (5) yields outlet flow area f in square inches.
    flow_area_in2 = (0.00209 * catchment_ft2 * rainfall_in_hr * sqrt(width_in)) ** (2 / 3)
    # For a rectangular box/valley section, depth is f / top water width.
    water_depth_in = flow_area_in2 / width_in
    flow_gpm = 4.167 * sqrt(flow_area_in2**3 / width_in)  # Eq. (4)
    return _result(
        "stormwater.as3500.csiro_1973_box_gutter",
        (),
        {
            "method": "historical empirical method, not AS/NZS 3500.3 Appendix H compliance",
            "source_reference": (
                "K.G. Martin, CSIRO DBR Technical Paper (Second Series) No. 1, "
                "Roof Drainage (1973), pp. 7-9, Eqs. (4)-(6)"
            ),
            "plan_catchment_area_m2": float(d["plan_catchment_area_m2"]),
            "sloping_area_factor": area_factor,
            "effective_catchment_area_ft2": catchment_ft2,
            "rainfall_intensity_in_per_hour": rainfall_in_hr,
            "water_width_mm": float(d["water_width_mm"]),
            "flow_area_mm2": flow_area_in2 * 25.4**2,
            "water_depth_mm": water_depth_in * 25.4,
            "calculated_flow_lps": flow_gpm * LPS_PER_IMPERIAL_GPM,
            "imperial_flow_gpm": flow_gpm,
        },
    )


def run_csiro_rainhead(inputs: dict[str, Any]) -> dict[str, Any]:
    """Solve the historical circular-downpipe receiver head using Martin (1973), Eqs 7-8."""
    d = _validated(inputs, CSIRO_RAINHEAD_SCHEMA)
    flow_lps = float(d["design_flow_lps"])
    diameter_mm = float(d["downpipe_diameter_mm"])
    if diameter_mm < 90:
        raise ValueError("Clause 3.7.8 minimum circular downpipe diameter is 90 mm")
    flow_gpm = flow_lps / LPS_PER_IMPERIAL_GPM
    diameter_in = diameter_mm / 25.4
    weir_head_in = (flow_gpm / (8.333 * diameter_in)) ** (2 / 3)
    if weir_head_in <= diameter_in / 3:
        head_in = weir_head_in
        relation = "weir"
    else:
        head_in = (flow_gpm / (2.777 * diameter_in**2)) ** 2
        relation = "orifice"
        if head_in < diameter_in / 3:
            raise ValueError(
                "CSIRO weir/orifice equations do not bracket the flow at the regime boundary"
            )
    clearance = d.get("box_side_clearance_mm")
    return _result(
        "stormwater.as3500.csiro_1973_rainhead",
        (),
        {
            "method": "historical empirical method, not AS/NZS 3500.3 Appendix H compliance",
            "source_reference": (
                "K.G. Martin, CSIRO DBR Technical Paper (Second Series) No. 1, "
                "Roof Drainage (1973), pp. 8-9, Eqs. (7)-(8)"
            ),
            "design_flow_lps": flow_lps,
            "downpipe_diameter_mm": diameter_mm,
            "receiver_head_relation": relation,
            "head_above_downpipe_mm": head_in * 25.4,
            "estimated_receiver_depth_mm": head_in / 0.6 * 25.4,
            "head_to_diameter_ratio": head_in / diameter_in,
            "minimum_head_diameter_ratio": 1 / 3 if relation == "orifice" else None,
            "side_clearance_mm": clearance,
            "side_clearance_recommendation_satisfied": (
                None if clearance is None else float(clearance) >= diameter_mm
            ),
        },
    )


def run_rainhead_design(inputs: dict[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, RAINHEAD_SCHEMA)
    q = float(d["design_flow_lps"])
    _limits(d, q)
    _, equivalent = _pipe(d["pipe"])
    pipe_context = {"pipe_family": _pipe_family(d["pipe"])}
    water, water_source = _appendix_i_upper_bracket(
        d.get("water_depth_chart"), q, "H.3.water_depth", pipe_context
    )
    depth = ceil(max(1.67 * water, 1.25 * equivalent))
    selected_depth = float(d.get("selected_depth_mm", depth))
    minimum_length, length_source = _appendix_i_upper_bracket(
        d.get("length_chart"),
        selected_depth,
        "H.3.length",
        {"gutter_depth_at_1_in_200_mm": float(d["gutter_depth_at_1_in_200_mm"])},
    )
    length = ceil(minimum_length)
    if d["pipe"]["shape"] == "circular":
        footprint = float(d["pipe"]["diameter_mm"])
    else:
        footprint = float(d["pipe"]["height_mm"])
        if float(d["pipe"]["width_mm"]) > float(d["box_width_mm"]):
            raise ValueError("Rectangular downpipe width exceeds rainhead width")
    clearance = float(d.get("pipe_edge_clearance_mm", 0))
    if (
        d["box_width_mm"]
        < (equivalent if d["pipe"]["shape"] == "circular" else d["pipe"]["width_mm"])
        + 2 * clearance
    ):
        raise ValueError("Rainhead width does not accommodate pipe and supplied edge clearances")
    length = ceil(max(length, footprint + 2 * clearance))
    selected_length = float(d.get("selected_length_mm", length))
    return _result(
        "stormwater.as3500.rainhead_design",
        ("3.7.4", "3.7.8", "H.2", "H.3"),
        {
            "design_flow_lps": q,
            "pipe_family": _pipe_family(d["pipe"]),
            "gutter_depth_at_1_in_200_mm": float(d["gutter_depth_at_1_in_200_mm"]),
            "water_depth_mm": water,
            "minimum_total_depth_mm": depth,
            "minimum_length_mm": length,
            "rainhead_width_mm": d["box_width_mm"],
            "selected_depth_mm": selected_depth,
            "selected_length_mm": selected_length,
            "selected_geometry_sufficient": selected_depth >= depth and selected_length >= length,
            "overflow_weir_below_top_mm": 25,
            "front_open_above_weir_required": True,
            "fully_sealed_to_gutter_required": True,
            "chart_values_supplied_by_designer": ("water_depth_chart" in d or "length_chart" in d),
            "chart_sources": [water_source, length_source],
            "chart_context": {
                "water_depth": {"pipe_family": _pipe_family(d["pipe"]), "flow_lps": q},
                "length": {
                    "gutter_depth_at_1_in_200_mm": float(d["gutter_depth_at_1_in_200_mm"]),
                    "adopted_rainhead_depth_mm": selected_depth,
                },
            },
            "rainhead_depth_used_for_length_chart_mm": selected_depth,
        },
    )


def _sump(d: dict) -> tuple[float, float, float, float, str, str]:
    q = sum(float(x) for x in d["gutter_flows_lps"]) + float(d.get("direct_roof_flow_lps", 0))
    _limits(d, q)
    _pipe(d["pipe"])
    sump, sump_source = _chart_or_appendix_i(
        d.get("sump_depth_chart"), q, "H.4", {"pipe_family": _pipe_family(d["pipe"])}
    )
    largest = max(d["gutter_flows_lps"])
    offset, offset_source = _chart_or_appendix_i(
        d.get("offset_chart"), largest, "H.6a", {"box_width_mm": d["box_width_mm"]}
    )
    return q, largest, sump, offset, sump_source, offset_source


def run_box_side_overflow(inputs: dict[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, SIDE_OVERFLOW_SCHEMA)
    q, largest, sump, offset, sump_source, offset_source = _sump(d)
    width = float(d["overflow_width_mm"])
    overflow, overflow_source = _chart_or_appendix_i(
        d.get("overflow_depth_chart"), q, "H.6b", {"overflow_width_mm": width}
    )
    depth = offset + overflow + 30
    return _result(
        "stormwater.as3500.box_side_overflow",
        ("3.7.4", "3.7.7", "H.4", "H.5", "H.6"),
        {
            "total_design_flow_lps": q,
            "largest_gutter_flow_lps": largest,
            "sump_depth_mm": ceil(sump),
            "offset_mm": offset,
            "overflow_width_mm": width,
            "overflow_depth_mm": ceil(overflow),
            "minimum_box_gutter_depth_mm": ceil(depth),
            "gutter_height_above_weir_mm": ceil(depth - 0.7 * offset),
            "overflow_sole_above_gutter_sole_mm": 0.7 * offset,
            "minimum_sump_width_mm": ceil(max(400, width + 2 * offset)),
            "minimum_sump_length_mm": d["box_width_mm"],
            "sump_dimension_along_gutter_mm": ceil(max(400, width + 2 * offset)),
            "sump_transverse_dimension_mm": d["box_width_mm"],
            "minimum_overflow_duct_gradient": 0.1
            if d.get("overflow_duct_length_mm", 0) > 450
            else 0,
            "normal_downpipe_assumed_fully_blocked": True,
            "overflow_to_atmosphere_required": True,
            "chart_values_supplied_by_designer": any(
                key in d for key in ("sump_depth_chart", "offset_chart", "overflow_depth_chart")
            ),
            "chart_sources": [sump_source, offset_source, overflow_source],
        },
    )


def run_box_high_capacity_overflow(inputs: dict[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, HIGH_OVERFLOW_SCHEMA)
    q, largest, sump, offset, sump_source, offset_source = _sump(d)
    height, height_source = _chart_or_appendix_i(
        d.get("height_chart"), largest, "H.8", {"box_width_mm": d["box_width_mm"]}
    )
    depth = max(float(d["free_discharge_gutter_depth_mm"]), height + offset)
    # H.7: downstream channel sole is 60 mm below crest.  When the crest
    # exceeds 60 mm, the datum is ABOVE the gutter sole (negative below).
    datum_below = 60 - offset if offset > 60 else 0
    return _result(
        "stormwater.as3500.box_high_capacity_overflow",
        ("3.7.4", "3.7.6", "3.7.7", "H.4", "H.6", "H.7", "H.8"),
        {
            "total_design_flow_lps": q,
            "largest_gutter_flow_lps": largest,
            "minimum_sump_depth_below_datum_mm": ceil(max(150, sump)),
            "sump_datum_below_gutter_sole_mm": datum_below,
            "minimum_sump_bottom_below_gutter_sole_mm": ceil(datum_below + max(150, sump)),
            "overflow_weir_crest_above_gutter_sole_mm": offset,
            "gutter_height_above_weir_mm": height,
            "minimum_box_gutter_depth_mm": ceil(depth),
            "sump_length_mm": 600,
            "sump_width_mm": d["box_width_mm"],
            "normal_downpipe_assumed_fully_blocked": True,
            "overflow_downpipe_design_flow_lps": q,
            "overflow_downpipe_capacity_requires_separate_check": True,
            "chart_values_supplied_by_designer": any(
                key in d for key in ("sump_depth_chart", "offset_chart", "height_chart")
            ),
            "chart_sources": [sump_source, offset_source, height_source],
        },
    )


CALCULATIONS = tuple(
    {
        "id": f"stormwater.as3500.{suffix}",
        "name": name,
        "description": description,
        "input_schema": schema,
        "runner": runner,
    }
    for suffix, name, description, schema, runner in [
        (
            "box_gutter_design",
            "Box gutter design",
            "Figure H.1 procedure using traceable chart data.",
            BOX_GUTTER_SCHEMA,
            run_box_gutter_design,
        ),
        (
            "box_gutter_hydraulics",
            "Box gutter hydraulic diagnostic",
            "Normal and critical depth diagnostic, separate from Figure H.1.",
            BOX_HYDRAULICS_SCHEMA,
            run_box_gutter_hydraulics,
        ),
        (
            "rainhead_design",
            "Rainhead design",
            "Figures H.2/H.3 geometry and downpipe checks.",
            RAINHEAD_SCHEMA,
            run_rainhead_design,
        ),
        (
            "box_side_overflow",
            "Box gutter side overflow",
            "Sump and side overflow procedure.",
            SIDE_OVERFLOW_SCHEMA,
            run_box_side_overflow,
        ),
        (
            "box_high_capacity_overflow",
            "Box gutter high capacity overflow",
            "Sump and high capacity overflow procedure.",
            HIGH_OVERFLOW_SCHEMA,
            run_box_high_capacity_overflow,
        ),
        (
            "csiro_1973_box_gutter",
            "CSIRO historical box gutter estimate",
            (
                "Chart-free historical box/valley gutter method from Martin (1973), "
                "Eqs. 4-6; not an AS/NZS 3500 design method."
            ),
            CSIRO_BOX_SCHEMA,
            run_csiro_box_gutter,
        ),
        (
            "csiro_1973_rainhead",
            "CSIRO historical rainhead estimate",
            (
                "Circular receiver head solved by Martin (1973), Eqs. 7-8; "
                "not an AS/NZS 3500 design method."
            ),
            CSIRO_RAINHEAD_SCHEMA,
            run_csiro_rainhead,
        ),
    ]
)
