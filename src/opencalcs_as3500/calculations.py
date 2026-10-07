"""Selected stormwater calculations with explicit units and bounded scope."""

from collections.abc import Mapping
from math import isfinite, radians, sqrt, tan
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from opencalcs_as3500.schemas import (
    DESIGN_FLOW_INPUT_SCHEMA,
    OPEN_CHANNEL_INPUT_SCHEMA,
    PERVIOUS_COEFFICIENT_INPUT_SCHEMA,
    PUMPED_STORAGE_INPUT_SCHEMA,
    ROOF_CATCHMENT_INPUT_SCHEMA,
    ROOF_FLOW_INPUT_SCHEMA,
    SAG_PIT_INPUT_SCHEMA,
)
from opencalcs_as3500.standards import (
    ROOF_RUNOFF_COEFFICIENTS,
    STANDARD,
)


def _check_finite(value: Any, path: str = "inputs") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _check_finite(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_finite(item, f"{path}[{index}]")
    elif isinstance(value, bool):
        return
    elif isinstance(value, (int, float)) and not isfinite(value):
        raise ValueError(f"{path} must contain only finite numbers")


def _validated(data: Mapping[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    values = dict(data)
    try:
        Draft202012Validator(schema).validate(values)
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path) or "inputs"
        raise ValueError(f"{location}: {exc.message}") from exc
    _check_finite(values)
    return values


def _result(calculation: str, clauses: tuple[str, ...], results: dict[str, Any]) -> dict[str, Any]:
    _check_finite(results, "results")
    return {
        "calculation": calculation,
        "standard": f"{STANDARD.code}:{STANDARD.edition}",
        "clauses": list(clauses),
        "results": results,
        "full_standard_compliance": False,
        "standard_compliance_evaluated": False,
    }


def run_roof_catchment(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate flat or single-slope, eaves-gutter roof catchment area."""

    data = _validated(inputs, ROOF_CATCHMENT_INPUT_SCHEMA)
    area = float(data["plan_area_m2"])
    slope = float(data["roof_slope_degrees"])
    factor = 1.0 if slope == 0 else 1.0 + 0.5 * tan(radians(slope))
    roof_case = "flat_roof" if slope == 0 else "single_slope_eaves_gutter"
    clauses = ("3.4.3.1",) if slope == 0 else ("3.4.3.2",)
    return _result(
        "stormwater.as3500.roof_catchment",
        clauses,
        {
            "plan_area_m2": area,
            "roof_slope_degrees": slope,
            "wind_exposure": data["wind_exposure"],
            "roof_case": roof_case,
            "catchment_area_factor": factor,
            "catchment_area_m2": area * factor,
        },
    )


def run_roof_flow(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate roof design flow using a supplied design rainfall intensity."""

    data = _validated(inputs, ROOF_FLOW_INPUT_SCHEMA)
    surface = data["roof_surface"]
    coefficient = ROOF_RUNOFF_COEFFICIENTS[surface]
    area = float(data["catchment_area_m2"])
    intensity = float(data["design_rainfall_intensity_mm_per_hour"])
    flow = coefficient * area * intensity / 3600.0
    return _result(
        "stormwater.as3500.roof_flow",
        ("5.4.6", "5.4.8"),
        {
            "catchment_area_m2": area,
            "design_rainfall_intensity_mm_per_hour": intensity,
            "roof_surface": surface,
            "runoff_coefficient": coefficient,
            "design_flow_lps": flow,
        },
    )


def run_pervious_coefficient(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate the Australian unroofed-pervious runoff coefficient."""

    data = _validated(inputs, PERVIOUS_COEFFICIENT_INPUT_SCHEMA)
    supplied_intensity = float(data["rainfall_10yr_60min_mm_per_hour"])
    intensity = min(70.0, max(25.0, supplied_intensity))
    multiplier = float(data["runoff_coefficient_multiplier_m"])
    soil = data["soil_type"]
    coefficient = multiplier * (0.0133 * intensity - 0.233)
    if soil == "clay":
        coefficient += 0.1
    elif soil == "sand":
        coefficient = max(0.1, coefficient - 0.1)
    if coefficient > 1.0:
        raise ValueError("calculated runoff coefficient exceeds 1.0")
    return _result(
        "stormwater.as3500.pervious_runoff_coefficient",
        ("5.4.6",),
        {
            "rainfall_10yr_60min_mm_per_hour": supplied_intensity,
            "intensity_used_mm_per_hour": intensity,
            "runoff_coefficient_multiplier_m": multiplier,
            "soil_type": soil,
            "runoff_coefficient": coefficient,
        },
    )


def run_design_flow(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate combined surface design flow from weighted subcatchments."""

    data = _validated(inputs, DESIGN_FLOW_INPUT_SCHEMA)
    intensity = float(data["design_rainfall_intensity_mm_per_hour"])
    effective_area = sum(
        float(item["area_m2"]) * float(item["runoff_coefficient"]) for item in data["catchments"]
    )
    flow = effective_area * intensity / 3600.0
    return _result(
        "stormwater.as3500.design_flow",
        ("5.4.7", "5.4.8"),
        {
            "design_rainfall_intensity_mm_per_hour": intensity,
            "catchment_count": len(data["catchments"]),
            "effective_area_m2": effective_area,
            "design_flow_lps": flow,
        },
    )


def run_open_channel_capacity(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate rectangular or trapezoidal open-channel capacity by Manning."""

    data = _validated(inputs, OPEN_CHANNEL_INPUT_SCHEMA)
    shape = data["shape"]
    width = float(data["bottom_width_m"])
    depth = float(data["flow_depth_m"])
    gradient = float(data["channel_gradient"])
    roughness = float(data["manning_n"])
    side_slope = float(data["side_slope_horizontal_to_vertical"]) if shape == "trapezoidal" else 0.0
    area = depth * (width + side_slope * depth)
    wetted_perimeter = width + 2.0 * depth * sqrt(1.0 + side_slope**2)
    hydraulic_radius = area / wetted_perimeter
    capacity = 1000.0 * area * hydraulic_radius ** (2.0 / 3.0) * sqrt(gradient) / roughness
    return _result(
        "stormwater.as3500.open_channel_capacity",
        ("5.4.9",),
        {
            "shape": shape,
            "flow_depth_m": depth,
            "flow_area_m2": area,
            "wetted_perimeter_m": wetted_perimeter,
            "hydraulic_radius_m": hydraulic_radius,
            "channel_gradient": gradient,
            "manning_n": roughness,
            "capacity_lps": capacity,
        },
    )


def run_sag_pit_capacity(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate sag-pit inlet capacity for ponding depths up to 120 mm."""

    data = _validated(inputs, SAG_PIT_INPUT_SCHEMA)
    depth = float(data["ponding_depth_m"])
    if depth > 0.12:
        raise ValueError("Clause 5.4.10.1 applies only when ponding depth is at most 0.12 m")
    perimeter = float(data["inlet_perimeter_m"])
    blockage = float(data.get("blockage_factor", 0.5))
    capacity = 1600.0 * blockage * perimeter * depth**1.5
    return _result(
        "stormwater.as3500.sag_pit_capacity",
        ("5.4.10.1",),
        {
            "inlet_perimeter_m": perimeter,
            "ponding_depth_m": depth,
            "blockage_factor": blockage,
            "capacity_lps": capacity,
        },
    )


def run_pumped_storage(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate the Clause 8.3.6 effective-storage and wet-well requirements."""

    data = _validated(inputs, PUMPED_STORAGE_INPUT_SCHEMA)
    area = float(data["catchment_area_m2"])
    coefficient = float(data["weighted_runoff_coefficient"])
    intensity = float(data["rainfall_10pct_120min_mm_per_hour"])
    pump_capacity = float(data["pump_capacity_lps"])
    storm_volume = area * coefficient * intensity * 2.0 / 1000.0
    pump_volume = pump_capacity * 30.0 * 60.0 / 1000.0
    minimum_wet_well = max(0.01 * area, 3.0)
    residual_storage = max(0.0, storm_volume - pump_volume)
    required_wet_well = max(minimum_wet_well, residual_storage)
    required_combined = pump_volume + required_wet_well
    available = data.get("available_wet_well_storage_m3")
    storage_satisfied = None
    provided_combined = None
    if available is not None:
        available = float(available)
        provided_combined = pump_volume + available
        storage_satisfied = available >= minimum_wet_well and provided_combined >= storm_volume
    return _result(
        "stormwater.as3500.pumped_storage",
        ("8.3.6",),
        {
            "catchment_area_m2": area,
            "weighted_runoff_coefficient": coefficient,
            "rainfall_10pct_120min_mm_per_hour": intensity,
            "storm_runoff_volume_m3": storm_volume,
            "pump_capacity_lps": pump_capacity,
            "pump_volume_in_30_min_m3": pump_volume,
            "minimum_wet_well_storage_m3": minimum_wet_well,
            "required_wet_well_storage_m3": required_wet_well,
            "required_combined_effective_storage_m3": required_combined,
            "available_wet_well_storage_m3": available,
            "provided_combined_effective_storage_m3": provided_combined,
            "storage_requirement_satisfied": storage_satisfied,
        },
    )
