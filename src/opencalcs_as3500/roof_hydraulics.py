# SPDX-License-Identifier: AGPL-3.0-only
"""Roof spreader sheet-flow and valley-gutter Manning diagnostics."""

from collections.abc import Mapping
from math import cos, isclose, radians, sin, sqrt, tan
from typing import Any

from opencalcs_as3500.calculations import _result, _validated

SPREADER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "upper_plan_area_m2",
        "lower_plan_area_m2",
        "upper_roof_slope_degrees",
        "lower_roof_slope_degrees",
        "rainfall_intensity_mm_per_hour",
        "upper_runoff_coefficient",
        "lower_runoff_coefficient",
        "spreader_width_m",
        "sheet_depth_m",
        "sheet_run_length_m",
        "receiving_surface_slope",
        "sheet_manning_n",
        "spreader_drop_m",
        "minor_loss_coefficient",
    ],
    "properties": {
        "upper_plan_area_m2": {"type": "number", "exclusiveMinimum": 0},
        "lower_plan_area_m2": {"type": "number", "minimum": 0},
        "upper_roof_slope_degrees": {"type": "number", "minimum": 0, "maximum": 80},
        "lower_roof_slope_degrees": {"type": "number", "minimum": 0, "maximum": 80},
        "rainfall_intensity_mm_per_hour": {"type": "number", "exclusiveMinimum": 0},
        "upper_runoff_coefficient": {"type": "number", "minimum": 0, "maximum": 1},
        "lower_runoff_coefficient": {"type": "number", "minimum": 0, "maximum": 1},
        "spreader_width_m": {"type": "number", "exclusiveMinimum": 0},
        "sheet_depth_m": {"type": "number", "exclusiveMinimum": 0},
        "sheet_run_length_m": {"type": "number", "exclusiveMinimum": 0},
        "receiving_surface_slope": {"type": "number", "exclusiveMinimum": 0},
        "sheet_manning_n": {"type": "number", "exclusiveMinimum": 0},
        "spreader_drop_m": {"type": "number", "minimum": 0},
        "minor_loss_coefficient": {"type": "number", "minimum": 0},
    },
}

VALLEY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "left_roof_slope_degrees",
        "right_roof_slope_degrees",
        "plan_angle_degrees",
        "bottom_width_m",
        "flow_depth_m",
        "channel_gradient",
        "manning_n",
        "design_rainfall_intensity_mm_per_hour",
        "contributing_plan_area_m2",
        "wave_allowance_m",
        "freeboard_m",
    ],
    "properties": {
        "left_roof_slope_degrees": {"type": "number", "exclusiveMinimum": 0, "maximum": 80},
        "right_roof_slope_degrees": {"type": "number", "exclusiveMinimum": 0, "maximum": 80},
        "plan_angle_degrees": {"type": "number", "exclusiveMinimum": 0, "maximum": 180},
        "bottom_width_m": {"type": "number", "exclusiveMinimum": 0},
        "flow_depth_m": {"type": "number", "exclusiveMinimum": 0},
        "channel_gradient": {"type": "number", "exclusiveMinimum": 0},
        "manning_n": {"type": "number", "exclusiveMinimum": 0},
        "design_rainfall_intensity_mm_per_hour": {"type": "number", "exclusiveMinimum": 0},
        "contributing_plan_area_m2": {"type": "number", "exclusiveMinimum": 0},
        "wave_allowance_m": {"type": "number", "minimum": 0},
        "freeboard_m": {"type": "number", "minimum": 0},
        "sheet_width_m": {"type": "number", "exclusiveMinimum": 0},
        "obstruction_width_m": {"type": "number", "minimum": 0},
    },
}

HIGHER_CATCHMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "upper_plan_area_m2",
        "upper_roof_slope_degrees",
        "lower_plan_area_m2",
        "lower_roof_slope_degrees",
        "design_rainfall_intensity_mm_per_hour",
        "lower_roof_material",
        "discharge_method",
    ],
    "properties": {
        "upper_plan_area_m2": {"type": "number", "exclusiveMinimum": 0},
        "upper_roof_slope_degrees": {"type": "number", "minimum": 0, "maximum": 65},
        "lower_plan_area_m2": {"type": "number", "minimum": 0},
        "lower_roof_slope_degrees": {"type": "number", "minimum": 0, "maximum": 65},
        "design_rainfall_intensity_mm_per_hour": {"type": "number", "exclusiveMinimum": 0},
        "lower_roof_material": {"type": "string", "enum": ["tiled", "corrugated_metal"]},
        "discharge_method": {"type": "string", "enum": ["spreader", "rainhead_or_sump"]},
        "treated_width_left_mm": {"type": "number", "minimum": 0},
        "treated_width_right_mm": {"type": "number", "minimum": 0},
        "sacked_to_eaves_per_as2050": {"type": "boolean"},
        "side_laps_sealed_full_length": {"type": "boolean"},
        "lower_gutter_capacity_lps": {"type": "number", "minimum": 0},
        "lower_downpipe_capacity_lps": {"type": "number", "minimum": 0},
        "rainhead_sump_capacity_lps": {"type": "number", "minimum": 0},
    },
}

VALLEY_STANDARD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "jurisdiction",
        "rainfall_duration_minutes",
        "design_rainfall_intensity_mm_per_hour",
        "catchment_area_m2",
        "left_roof_slope_degrees",
        "right_roof_slope_degrees",
        "valley_side_angle_degrees",
        "obstructed_below_effective_width",
    ],
    "properties": {
        "jurisdiction": {"type": "string", "enum": ["AU", "NZ"]},
        "rainfall_duration_minutes": {"type": "number", "enum": [5]},
        "design_rainfall_intensity_mm_per_hour": {"type": "number", "exclusiveMinimum": 0},
        "catchment_area_m2": {"type": "number", "exclusiveMinimum": 0},
        "left_roof_slope_degrees": {"type": "number", "minimum": 0},
        "right_roof_slope_degrees": {"type": "number", "minimum": 0},
        "valley_side_angle_degrees": {"type": "number", "exclusiveMinimum": 0},
        "obstructed_below_effective_width": {"type": "boolean"},
        "available_effective_width_mm": {"type": "number", "minimum": 0},
        "available_sheet_width_mm": {"type": "number", "minimum": 0},
        "available_total_gutter_depth_mm": {"type": "number", "minimum": 0},
    },
}


def run_roof_spreader(inputs: Mapping[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, SPREADER_SCHEMA)
    i = float(d["rainfall_intensity_mm_per_hour"])
    au = float(d["upper_plan_area_m2"])
    al = float(d["lower_plan_area_m2"])
    # Clause 3.4.3 sloping exposed-roof catchment factor, used independently per roof.
    fu = 1 + 0.5 * tan(radians(float(d["upper_roof_slope_degrees"])))
    fl = 1 + 0.5 * tan(radians(float(d["lower_roof_slope_degrees"])))
    qu = au * fu * float(d["upper_runoff_coefficient"]) * i / 3600
    ql = al * fl * float(d["lower_runoff_coefficient"]) * i / 3600
    # Broad, shallow, rectangular sheet: Manning area=b*y and wetted perimeter=b+2y.
    b = float(d["spreader_width_m"])
    y = float(d["sheet_depth_m"])
    slope = float(d["receiving_surface_slope"])
    n = float(d["sheet_manning_n"])
    run = float(d["sheet_run_length_m"])
    drop = float(d["spreader_drop_m"])
    base_energy_slope = slope + drop / run
    k = float(d["minor_loss_coefficient"])

    def sheet_capacity(width: float) -> float:
        section_area = width * y
        hydraulic_radius = section_area / (width + 2 * y)
        no_loss_capacity = (
            1000 / n * section_area * hydraulic_radius ** (2 / 3) * sqrt(base_energy_slope)
        )
        lo_q, hi_q = 0.0, no_loss_capacity
        for _ in range(80):
            mid_q = (lo_q + hi_q) / 2
            velocity_at_q = mid_q / 1000 / section_area
            loss_slope = k * velocity_at_q**2 / (2 * 9.80665 * run)
            effective_slope = max(0.0, base_energy_slope - loss_slope)
            conveyance = (
                1000 / n * section_area * hydraulic_radius ** (2 / 3) * sqrt(effective_slope)
            )
            if conveyance > mid_q:
                lo_q = mid_q
            else:
                hi_q = mid_q
        return (lo_q + hi_q) / 2

    area = b * y
    radius = area / (b + 2 * y)
    capacity = sheet_capacity(b)
    qrequired = qu
    width_required = 0.0
    if qrequired:
        lo, hi = 0.0, max(b, 2 * y)
        while sheet_capacity(hi) < qrequired:
            hi *= 2
        for _ in range(80):
            mid = (lo + hi) / 2
            if sheet_capacity(mid) < qrequired:
                lo = mid
            else:
                hi = mid
        width_required = (lo + hi) / 2
    velocity = (qu / 1000 / area) if area else 0
    loss_head = k * velocity**2 / (2 * 9.80665)
    energy_slope = max(0.0, base_energy_slope - loss_head / run)
    return _result(
        "stormwater.as3500.roof_spreader_sheet_flow",
        (),
        {
            "upper_effective_catchment_area_m2": au * fu,
            "lower_effective_catchment_area_m2": al * fl,
            "upper_flow_lps": qu,
            "lower_local_flow_lps": ql,
            "combined_lower_discharge_lps": qu + ql,
            "spreader_width_m": b,
            "sheet_depth_m": y,
            "sheet_flow_area_m2": area,
            "hydraulic_radius_m": radius,
            "sheet_run_length_m": run,
            "effective_energy_slope": energy_slope,
            "sheet_capacity_lps": capacity,
            "required_sheet_width_m": width_required,
            "sheet_capacity_satisfied": capacity + 1e-12 >= qu,
            "spreader_drop_m": drop,
            "specified_minor_loss_coefficient": k,
            "estimated_minor_loss_head_m": loss_head,
            "adequacy_status": (
                "hydraulic_sheet_capacity_only; spreader distribution, edge effects, "
                "roof detailing, "
                "receiving gutter and applicable placement/detail requirements are not evaluated"
            ),
            "method": (
                "Manning open-sheet approximation for supplied rectangular sheet depth and "
                "roughness; no proprietary spreader fit is used."
            ),
        },
    )


def run_valley_gutter(inputs: Mapping[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, VALLEY_SCHEMA)
    a, b, theta = (
        radians(float(d[k]))
        for k in ("left_roof_slope_degrees", "right_roof_slope_degrees", "plan_angle_degrees")
    )
    gx, gy = tan(a) - tan(b) * cos(theta), -tan(b) * sin(theta)
    norm = sqrt(gx * gx + gy * gy)
    if norm < 1e-12:
        raise ValueError(
            "equal roof slopes with zero plan angle do not define a unique valley cross-section"
        )
    tx, ty = gx / norm, gy / norm
    left_grade = abs(tan(a) * tx)
    right_grade = abs(tan(b) * (tx * cos(theta) + ty * sin(theta)))
    if left_grade <= 1e-12 or right_grade <= 1e-12:
        raise ValueError(
            "roof geometry gives a vertical valley side; revise slope/plan-angle inputs"
        )
    zl, zr = 1 / left_grade, 1 / right_grade
    depth, width = float(d["flow_depth_m"]), float(d["bottom_width_m"])
    gradient, roughness = float(d["channel_gradient"]), float(d["manning_n"])
    qdesign = (
        float(d["contributing_plan_area_m2"])
        * float(d["design_rainfall_intensity_mm_per_hour"])
        / 3600
    )
    qdesign_m3s = qdesign / 1000
    g = 9.80665

    def section_area(y):
        return y * (width + (zl + zr) * y / 2)

    def top_width(y):
        return width + (zl + zr) * y

    def manning_flow(y):
        area = section_area(y)
        perimeter = width + y * sqrt(1 + zl**2) + y * sqrt(1 + zr**2)
        return area * (area / perimeter) ** (2 / 3) * sqrt(gradient) / roughness

    area = section_area(depth)
    perimeter = width + depth * sqrt(1 + zl**2) + depth * sqrt(1 + zr**2)
    radius = area / perimeter
    qcap = area * radius ** (2 / 3) * sqrt(gradient) / roughness
    normal = critical = 0.0
    if qdesign_m3s:
        lo, hi = 0.0, max(depth, 0.01)
        while manning_flow(hi) < qdesign_m3s:
            hi *= 2
        for _ in range(100):
            mid = (lo + hi) / 2
            if manning_flow(mid) < qdesign_m3s:
                lo = mid
            else:
                hi = mid
        normal = (lo + hi) / 2

        def froude(y):
            return qdesign_m3s**2 * top_width(y) / (g * section_area(y) ** 3) - 1

        lo, hi = 1e-9, max(depth * 8, 0.1)
        while froude(hi) > 0:
            hi *= 2
        for _ in range(100):
            mid = (lo + hi) / 2
            if froude(mid) > 0:
                lo = mid
            else:
                hi = mid
        critical = (lo + hi) / 2
    sheet = float(d.get("sheet_width_m", width + (zl + zr) * depth))
    obstruction = float(d.get("obstruction_width_m", 0))
    wave, freeboard = float(d["wave_allowance_m"]), float(d["freeboard_m"])
    ycheck = depth + wave + freeboard
    acheck = section_area(ycheck)
    pcheck = width + ycheck * sqrt(1 + zl**2) + ycheck * sqrt(1 + zr**2)
    geom_capacity = 1000 * acheck * (acheck / pcheck) ** (2 / 3) * sqrt(gradient) / roughness

    def rect_capacity(w):
        ar = w * depth
        return 1000 * ar * (ar / (w + 2 * depth)) ** (2 / 3) * sqrt(gradient) / roughness

    lo, hi = 0.0, max(width, depth)
    while rect_capacity(hi) < qdesign:
        hi *= 2
    for _ in range(100):
        mid = (lo + hi) / 2
        if rect_capacity(mid) < qdesign:
            lo = mid
        else:
            hi = mid
    return _result(
        "stormwater.as3500.valley_gutter_manning_check",
        ("3.6",),
        {
            "left_side_slope_horizontal_to_vertical": zl,
            "right_side_slope_horizontal_to_vertical": zr,
            "cross_section_area_m2": area,
            "wetted_perimeter_m": perimeter,
            "hydraulic_radius_m": radius,
            "flow_depth_m": depth,
            "normal_depth_m_at_design_flow": normal,
            "critical_depth_m_at_design_flow": critical,
            "capacity_lps": 1000 * qcap,
            "design_flow_lps": qdesign,
            "capacity_excess_lps": 1000 * qcap - qdesign,
            "capacity_satisfied": qcap >= qdesign_m3s,
            "sheet_width_m": sheet,
            "obstruction_width_m": obstruction,
            "effective_sheet_width_m": max(0, sheet - obstruction),
            "wave_allowance_m": wave,
            "freeboard_m": freeboard,
            "geometric_check_depth_m": ycheck,
            "capacity_at_depth_plus_wave_and_freeboard_lps": geom_capacity,
            "rectangular_box_section_screening_width_m_at_flow_depth": (lo + hi) / 2,
            "rectangular_box_section_capacity_lps_at_flow_depth": rect_capacity((lo + hi) / 2),
            "adequacy_status": (
                "Manning diagnostic only; standard selection and construction checks are separate."
            ),
            "limitations": [
                "not CFD equivalent",
                "does not establish AS/NZS 3500.3 valley sizing compliance",
                "caller-supplied wave allowance is not inferred",
                "plan angle/slope-derived side slopes idealize intersecting planar roofs",
            ],
        },
    )


def run_higher_catchment(inputs: Mapping[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, HIGHER_CATCHMENT_SCHEMA)
    intensity = float(d["design_rainfall_intensity_mm_per_hour"])
    upper_area, lower_area = float(d["upper_plan_area_m2"]), float(d["lower_plan_area_m2"])
    fu = 1 + 0.5 * tan(radians(float(d["upper_roof_slope_degrees"])))
    fl = 1 + 0.5 * tan(radians(float(d["lower_roof_slope_degrees"])))
    upper_flow, lower_flow = upper_area * fu * intensity / 3600, lower_area * fl * intensity / 3600
    combined = upper_flow + lower_flow
    material, method = d["lower_roof_material"], d["discharge_method"]
    findings = []
    left = float(d.get("treated_width_left_mm", 0))
    right = float(d.get("treated_width_right_mm", 0))
    detail = None
    if method == "spreader":
        if left < 1800 or right < 1800:
            findings.append("treated strip must extend at least 1800 mm on each side")
        if material == "tiled" and not d.get("sacked_to_eaves_per_as2050", False):
            findings.append("tiled receiving roof must be sacked to the eaves per AS 2050")
        if material == "corrugated_metal" and not d.get("side_laps_sealed_full_length", False):
            findings.append("corrugated-metal side laps must be sealed for their full length")
        detail = not findings
    else:
        left = right = None
    gutter, downpipe, receiver = (
        d.get(k)
        for k in (
            "lower_gutter_capacity_lps",
            "lower_downpipe_capacity_lps",
            "rainhead_sump_capacity_lps",
        )
    )
    result = {
        "upper_effective_catchment_area_m2": upper_area * fu,
        "lower_effective_catchment_area_m2": lower_area * fl,
        "upper_flow_lps": upper_flow,
        "lower_local_flow_lps": lower_flow,
        "combined_lower_discharge_lps": combined,
        "discharge_method": method,
        "lower_roof_material": material,
        "treated_width_left_mm": left,
        "treated_width_right_mm": right,
        "spreader_detail_satisfied": detail,
        "spreader_detail_findings": findings,
        "lower_gutter_capacity_lps": gutter,
        "lower_gutter_capacity_satisfied": None if gutter is None else float(gutter) >= combined,
        "lower_downpipe_capacity_lps": downpipe,
        "lower_downpipe_capacity_satisfied": None
        if downpipe is None
        else float(downpipe) >= combined,
        "rainhead_sump_capacity_lps": receiver,
        "rainhead_sump_capacity_satisfied": None
        if receiver is None
        else float(receiver) >= combined,
        "overflow_assessment_required": True,
        "adequacy_status": (
            "screening only; verify the receiver and downstream conveyance for combined flow "
            "and assess overflow."
        ),
    }
    return _result("stormwater.as3500.higher_catchment_diagnostic", ("3.4.5",), result)


def run_standard_valley_selection(inputs: Mapping[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, VALLEY_STANDARD_SCHEMA)
    area = float(d["catchment_area_m2"])
    intensity = float(d["design_rainfall_intensity_mm_per_hour"])
    duration = float(d["rainfall_duration_minutes"])
    if d["jurisdiction"] != "AU":
        raise ValueError("verified Table/Figure 3.6.2 selection data in this runner is Australian")
    if area > 40:
        raise ValueError("catchment_area_m2 exceeds the verified Figure 3.6.2 range of 40 m2")
    if duration != 5.0:
        raise ValueError("Australian valley selection requires the 5-minute rainfall duration")
    if area <= 20:
        if intensity > 400:
            raise ValueError("Table 3.6.2 has no selection above 400 mm/h")
        rows = [
            (200, 355, 32, 215),
            (250, 375, 35, 234),
            (300, 395, 38, 254),
            (350, 415, 40, 273),
            (400, 435, 43, 292),
        ]
        sheet_width, effective_depth, effective_width = next(
            row[1:] for row in rows if intensity <= row[0]
        )
        basis, chart = "Table 3.6.2 row selection through 20 m2", False
        required_freeboard = 15
        total_depth = effective_depth + required_freeboard
    else:
        raise ValueError(
            "Figure 3.6.2 chart axes/data need verification before selecting areas above 20 m2"
        )
    findings = []
    left, right = float(d["left_roof_slope_degrees"]), float(d["right_roof_slope_degrees"])
    if left < 12.5 or right < 12.5:
        findings.append("roof slope below the 12.5 degree selection minimum")
    side_angle = float(d["valley_side_angle_degrees"])
    nominal_side_angle = 16.5
    if not isclose(side_angle, nominal_side_angle, abs_tol=0.05):
        findings.append("valley side angle differs from the nominal 16.5 degrees (1:3.4)")
    if d["obstructed_below_effective_width"]:
        findings.append("effective cross-sectional area below selected width is obstructed")
    available = {
        "effective_width": d.get("available_effective_width_mm"),
        "sheet_width": d.get("available_sheet_width_mm"),
        "total_gutter_depth": d.get("available_total_gutter_depth_mm"),
    }
    checks = {
        f"{key}_satisfied": None if value is None else float(value) >= required
        for (key, value), required in zip(
            available.items(), (effective_width, sheet_width, total_depth), strict=True
        )
    }
    return _result(
        "stormwater.as3500.valley_gutter_standard_selection",
        ("3.6",),
        {
            "jurisdiction": "AU",
            "rainfall_duration_minutes": duration,
            "design_rainfall_intensity_mm_per_hour": intensity,
            "catchment_area_m2": area,
            "selected_sheet_width_mm": sheet_width,
            "selected_effective_width_mm": effective_width,
            "selected_effective_depth_mm": effective_depth,
            "required_freeboard_mm": required_freeboard,
            "selected_total_gutter_depth_mm": total_depth,
            "nominal_valley_side_angle_degrees": nominal_side_angle,
            "input_valley_side_angle_degrees": side_angle,
            "chart_based_selection": chart,
            "selection_basis": basis,
            "available_effective_width_mm": available["effective_width"],
            "available_sheet_width_mm": available["sheet_width"],
            "available_total_gutter_depth_mm": available["total_gutter_depth"],
            **checks,
            "selection_findings": findings,
            "selection_satisfied": not findings and all(v is not False for v in checks.values()),
            "limitations": [
                "Figure 3.6.2 selection above 20 m2 remains guarded because its apparent rising "
                "DRI-versus-area curves conflict with older editions' 20 m2 table limit.",
                "The runner does not select site-specific rainfall intensity or assess all "
                "detailing requirements.",
            ],
        },
    )


CALCULATIONS = (
    {
        "id": "stormwater.as3500.higher_catchment_diagnostic",
        "name": "Higher catchment spreader detail",
        "description": "Clause 3.4.5 treated-strip checks and combined downstream flow screening.",
        "input_schema": HIGHER_CATCHMENT_SCHEMA,
        "runner": run_higher_catchment,
    },
    {
        "id": "stormwater.as3500.valley_gutter_standard_selection",
        "name": "Valley gutter standard selection",
        "description": (
            "Clause 3.6 Table/Figure selection of sheet width, effective width and depth."
        ),
        "input_schema": VALLEY_STANDARD_SCHEMA,
        "runner": run_standard_valley_selection,
    },
    {
        "id": "stormwater.as3500.roof_spreader_sheet_flow",
        "name": "Roof spreader sheet-flow check",
        "description": (
            "Upper/lower catchment accounting and Manning sheet capacity for supplied geometry."
        ),
        "input_schema": SPREADER_SCHEMA,
        "runner": run_roof_spreader,
    },
    {
        "id": "stormwater.as3500.valley_gutter_manning_check",
        "name": "Valley gutter Manning diagnostic",
        "description": (
            "Slope/plan-angle-derived valley section with Manning and explicit wave/freeboard "
            "checks; not CFD or AS/NZS 3500.3 chart sizing."
        ),
        "input_schema": VALLEY_SCHEMA,
        "runner": run_valley_gutter,
    },
)
