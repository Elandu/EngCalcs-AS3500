"""JSON schemas for calculation inputs and outputs."""

from opencalcs_as3500.standards import PERVIOUS_RUNOFF_MULTIPLIERS

POSITIVE = {"type": "number", "exclusiveMinimum": 0}
NON_NEGATIVE = {"type": "number", "minimum": 0}

ROOF_CATCHMENT_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["plan_area_m2", "roof_slope_degrees", "wind_exposure"],
    "properties": {
        "plan_area_m2": POSITIVE,
        "roof_slope_degrees": {"type": "number", "minimum": 0, "maximum": 65},
        "wind_exposure": {"type": "string", "enum": ["freely_exposed"]},
    },
}

ROOF_FLOW_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["catchment_area_m2", "design_rainfall_intensity_mm_per_hour", "roof_surface"],
    "properties": {
        "catchment_area_m2": POSITIVE,
        "design_rainfall_intensity_mm_per_hour": POSITIVE,
        "roof_surface": {
            "type": "string",
            "enum": list(("steel_non_absorbent", "near_flat_slightly_absorbent")),
        },
    },
}

PERVIOUS_COEFFICIENT_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "rainfall_10yr_60min_mm_per_hour",
        "runoff_coefficient_multiplier_m",
        "soil_type",
    ],
    "properties": {
        "rainfall_10yr_60min_mm_per_hour": POSITIVE,
        "runoff_coefficient_multiplier_m": {
            "type": "number",
            "enum": list(PERVIOUS_RUNOFF_MULTIPLIERS),
        },
        "soil_type": {"type": "string", "enum": ["other", "clay", "sand"]},
    },
}

DESIGN_FLOW_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["design_rainfall_intensity_mm_per_hour", "catchments"],
    "properties": {
        "design_rainfall_intensity_mm_per_hour": POSITIVE,
        "catchments": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["area_m2", "runoff_coefficient"],
                "properties": {
                    "area_m2": POSITIVE,
                    "runoff_coefficient": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
    },
}

OPEN_CHANNEL_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "shape",
        "bottom_width_m",
        "flow_depth_m",
        "channel_gradient",
        "manning_n",
    ],
    "properties": {
        "shape": {"type": "string", "enum": ["rectangular", "trapezoidal"]},
        "bottom_width_m": POSITIVE,
        "flow_depth_m": POSITIVE,
        "channel_gradient": POSITIVE,
        "manning_n": POSITIVE,
        "side_slope_horizontal_to_vertical": NON_NEGATIVE,
    },
    "allOf": [
        {
            "if": {"properties": {"shape": {"const": "trapezoidal"}}},
            "then": {
                "required": ["side_slope_horizontal_to_vertical"],
                "properties": {
                    "side_slope_horizontal_to_vertical": POSITIVE,
                },
            },
        }
    ],
}

SAG_PIT_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["inlet_perimeter_m", "ponding_depth_m"],
    "properties": {
        "inlet_perimeter_m": POSITIVE,
        "ponding_depth_m": POSITIVE,
        "blockage_factor": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
    },
}

PUMPED_STORAGE_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "catchment_area_m2",
        "weighted_runoff_coefficient",
        "rainfall_10pct_120min_mm_per_hour",
        "pump_capacity_lps",
    ],
    "properties": {
        "catchment_area_m2": POSITIVE,
        "weighted_runoff_coefficient": {"type": "number", "minimum": 0, "maximum": 1},
        "rainfall_10pct_120min_mm_per_hour": POSITIVE,
        "pump_capacity_lps": POSITIVE,
        "available_wet_well_storage_m3": NON_NEGATIVE,
    },
}

OUTPUT_SCHEMA = {
    "type": "object",
    "required": [
        "calculation",
        "standard",
        "clauses",
        "results",
        "full_standard_compliance",
        "standard_compliance_evaluated",
    ],
    "properties": {
        "calculation": {"type": "string"},
        "standard": {"type": "string"},
        "clauses": {"type": "array", "items": {"type": "string"}},
        "results": {"type": "object"},
        "full_standard_compliance": {"const": False},
        "standard_compliance_evaluated": {"const": False},
    },
    "additionalProperties": True,
}
