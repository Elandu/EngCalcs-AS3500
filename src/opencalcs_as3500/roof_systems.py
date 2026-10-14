# SPDX-License-Identifier: AGPL-3.0-only

"""Expanded roof catchment and eaves-gutter design methods.

AS/NZS Figure 3.5.5 has a chart-based sizing runner and an optional exact
manufacturer-rating check. A separate historical CSIRO calculation implements
the 1973 Martin method and is not presented as current AS/NZS compliance.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import pairwise
from math import ceil, sqrt
from typing import Any

from opencalcs_as3500.calculations import _result, _validated

POS = {"type": "number", "exclusiveMinimum": 0}
NONNEG = {"type": "number", "minimum": 0}
AREA = {"type": "number", "exclusiveMinimum": 0, "unit": "m2"}

_COMMON_CATCHMENT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["catchment_id", "geometry"],
    "properties": {
        "catchment_id": {"type": "string", "minLength": 1},
        "geometry": {
            "type": "string",
            "enum": [
                "flat_roof",
                "single_slope_freely_exposed",
                "single_slope_partially_exposed",
                "adjacent_sloping_roofs",
                "vertical_wall_flat_roof",
                "vertical_wall_sloping_roof",
                "perpendicular_vertical_walls",
            ],
        },
        "plan_area_m2": AREA,
        "roof_slope_degrees": {"type": "number", "minimum": 0, "maximum": 65},
        "plan_area_1_m2": AREA,
        "plan_area_2_m2": AREA,
        "vertical_areas_m2": {"type": "array", "minItems": 2, "maxItems": 4, "items": NONNEG},
        "vertical_area_1_m2": NONNEG,
        "vertical_area_2_m2": NONNEG,
        "vertical_area_m2": NONNEG,
        "exposed_wall_height_m": POS,
        "wind_scenarios": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["direction_id"],
                "properties": {
                    "direction_id": {"type": "string", "minLength": 1},
                    "vertical_areas_m2": {
                        "type": "array",
                        "minItems": 4,
                        "maxItems": 4,
                        "items": NONNEG,
                    },
                    "vertical_area_1_m2": NONNEG,
                    "vertical_area_2_m2": NONNEG,
                    "vertical_area_m2": NONNEG,
                },
            },
        },
    },
}
ROOF_CATCHMENT_PLAN_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["catchments"],
    "properties": {
        "catchments": {
            "type": "array",
            "minItems": 1,
            "items": {
                **_COMMON_CATCHMENT,
                "allOf": [
                    {
                        "if": {"properties": {"geometry": {"const": "flat_roof"}}},
                        "then": {"required": ["plan_area_m2"]},
                    },
                    {
                        "if": {
                            "properties": {"geometry": {"const": "single_slope_freely_exposed"}}
                        },
                        "then": {"required": ["plan_area_m2", "roof_slope_degrees"]},
                    },
                    {
                        "if": {
                            "properties": {"geometry": {"const": "single_slope_partially_exposed"}}
                        },
                        "then": {
                            "required": ["plan_area_m2", "roof_slope_degrees", "vertical_areas_m2"],
                            "properties": {"vertical_areas_m2": {"minItems": 4, "maxItems": 4}},
                        },
                    },
                    {
                        "if": {"properties": {"geometry": {"const": "adjacent_sloping_roofs"}}},
                        "then": {
                            "required": [
                                "plan_area_1_m2",
                                "plan_area_2_m2",
                                "vertical_area_1_m2",
                                "vertical_area_2_m2",
                            ]
                        },
                    },
                    {
                        "if": {"properties": {"geometry": {"const": "vertical_wall_flat_roof"}}},
                        "then": {"required": ["plan_area_m2", "vertical_area_m2"]},
                    },
                    {
                        "if": {
                            "properties": {
                                "geometry": {
                                    "enum": [
                                        "vertical_wall_sloping_roof",
                                        "perpendicular_vertical_walls",
                                    ]
                                }
                            }
                        },
                        "then": {
                            "required": ["plan_area_m2", "vertical_area_1_m2", "vertical_area_2_m2"]
                        },
                    },
                    {
                        "if": {
                            "properties": {"geometry": {"const": "single_slope_partially_exposed"}}
                        },
                        "then": {
                            "properties": {
                                "wind_scenarios": {
                                    "items": {"required": ["direction_id", "vertical_areas_m2"]}
                                }
                            }
                        },
                    },
                    {
                        "if": {"properties": {"geometry": {"const": "adjacent_sloping_roofs"}}},
                        "then": {
                            "properties": {
                                "wind_scenarios": {
                                    "items": {
                                        "required": [
                                            "direction_id",
                                            "vertical_area_1_m2",
                                            "vertical_area_2_m2",
                                        ]
                                    }
                                }
                            }
                        },
                    },
                    {
                        "if": {"properties": {"geometry": {"const": "vertical_wall_flat_roof"}}},
                        "then": {
                            "properties": {
                                "wind_scenarios": {
                                    "items": {"required": ["direction_id", "vertical_area_m2"]}
                                }
                            }
                        },
                    },
                    {
                        "if": {
                            "properties": {
                                "geometry": {
                                    "enum": [
                                        "vertical_wall_sloping_roof",
                                        "perpendicular_vertical_walls",
                                    ]
                                }
                            }
                        },
                        "then": {
                            "properties": {
                                "wind_scenarios": {
                                    "items": {
                                        "required": [
                                            "direction_id",
                                            "vertical_area_1_m2",
                                            "vertical_area_2_m2",
                                        ]
                                    }
                                }
                            }
                        },
                    },
                ],
            },
        }
    },
}

_TABLE_352 = [
    # effective gutter area for gradient >= 1:500, flatter; pipe mm; pipe mm
    (3500, 4700, 65, "circular", "65x50"),
    (4200, 5600, 75, "circular", "65x50"),
    (4600, 6200, 75, "circular", "75x50"),
    (4800, 6400, 80, "circular", "75x50"),
    (5200, 7000, 80, "circular", "100x50"),
    (5900, 7900, 85, "circular", "100x50"),
    (6400, 8600, 90, "circular", "100x50"),
    (6600, 8900, 90, "circular", "75x70"),
    (6700, 9000, 100, "circular", "75x70"),
    (8200, 11000, 100, "circular", "100x75"),
    (9600, 12900, 125, "circular", "100x75"),
    (12800, 17100, 125, "circular", "100x100"),
    (12800, 17200, 150, "circular", "100x100"),
    (16000, 21500, 150, "circular", "125x100"),
    (18400, 24700, 150, "circular", "150x100"),
    (19200, 25800, None, "rectangular_or_square", "150x100"),
    (20000, 26800, None, "rectangular_or_square", "125x125"),
]

_CSIRO_OUTLET_FACTORS = {
    "central": 1.00,
    "slightly_displaced": 0.66,
    "considerably_displaced": 0.33,
    "end": 0.0,
}
_CSIRO_BEND_FACTORS = {
    "less_than_6_ft": {"sloping": -0.25, "level": -0.20},
    "6_to_12_ft": {"sloping": -0.125, "level": -0.10},
    "greater_than_12_ft": {"sloping": 0.0, "level": 0.0},
}

_OVERFLOW_BACK_GAP = {
    4: {1.5: 0.6, 3.0: 0.8, 4.5: 0.8, 6.0: 0.8},
    6: {1.5: 1.0, 3.0: 1.2, 4.5: 1.3, 6.0: 1.3},
    8: {1.5: 1.4, 3.0: 1.6, 4.5: 1.7, 6.0: 1.8},
    10: {1.5: 1.8, 3.0: 2.0, 4.5: 2.1, 6.0: 2.2},
    12: {1.5: 2.0, 3.0: 2.4, 4.5: 2.5, 6.0: 2.6},
}

EAVES_SYSTEM_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "design_rainfall_intensity_mm_per_hour",
        "gradient",
        "effective_gutter_area_mm2",
        "manufacturer_ratings",
        "downpipe_catchments_m2",
    ],
    "properties": {
        "design_rainfall_intensity_mm_per_hour": POS,
        "gradient": POS,
        "effective_gutter_area_mm2": POS,
        "manufacturer_ratings": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "effective_gutter_area_mm2",
                    "rainfall_intensity_mm_per_hour",
                    "gradient",
                    "maximum_catchment_area_per_downpipe_m2",
                    "source",
                ],
                "properties": {
                    "effective_gutter_area_mm2": POS,
                    "rainfall_intensity_mm_per_hour": POS,
                    "gradient": POS,
                    "maximum_catchment_area_per_downpipe_m2": POS,
                    "source": {"type": "string", "minLength": 1},
                },
            },
        },
        "downpipe_catchments_m2": {"type": "array", "minItems": 1, "items": AREA},
    },
}

EAVES_CHART_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "catchment_area_m2",
        "design_rainfall_intensity_mm_per_hour",
        "gradient",
        "downpipe_count",
    ],
    "properties": {
        "catchment_area_m2": AREA,
        "design_rainfall_intensity_mm_per_hour": POS,
        "gradient": POS,
        "downpipe_count": {"type": "integer", "minimum": 1},
    },
}

# Conservative readings of the dual flow/effective-area axes in AS/NZS
# 3500.3:2025 Figures 3.5.5(A) and (B). Values are paired as (flow L/s,
# effective area mm2). The Appendix G.2 worked check anchors Figure A at
# 2.054 L/s / 7,300 mm2. Between readings, the next higher flow tick is used
# as an upper bracket. These values encode chart readings, not the source art.
_EAVES_CHART_POINTS = {
    "1:500_and_steeper": (
        (0.68, 3000),
        (1.0, 4000),
        (1.5, 5500),
        (2.0, 7000),
        (2.054, 7300),
        (2.5, 8500),
        (3.0, 10000),
        (3.5, 11500),
        (4.0, 13000),
        (4.5, 14500),
        (5.0, 16000),
        (5.5, 17000),
        (6.0, 18000),
    ),
    "flatter_than_1:500": (
        (0.68, 3000),
        (1.0, 4000),
        (1.5, 6000),
        (2.0, 8000),
        (2.5, 10000),
        (3.0, 12000),
        (3.5, 14000),
        (4.0, 16000),
        (4.5, 18000),
        (5.0, 20000),
        (5.5, 22000),
        (6.0, 24000),
    ),
}

CSIRO_EAVES_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "catchment_area_m2",
        "rainfall_intensity_mm_per_hour",
        "gutter_slope_condition",
        "bend_distance_category",
        "outlet_position",
        "cross_section_type",
    ],
    "properties": {
        "catchment_area_m2": AREA,
        "rainfall_intensity_mm_per_hour": POS,
        "gutter_slope_condition": {"type": "string", "enum": ["sloping", "level"]},
        "bend_distance_category": {
            "type": "string",
            "enum": ["less_than_6_ft", "6_to_12_ft", "greater_than_12_ft"],
        },
        "outlet_position": {
            "type": "string",
            "enum": ["central", "slightly_displaced", "considerably_displaced", "end"],
        },
        "cross_section_type": {"type": "string", "enum": ["rounded", "rectangular"]},
        "gradient": POS,
        "product_catalog": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "product_id",
                    "gross_cross_section_area_mm2",
                    "effective_cross_sectional_area_mm2",
                ],
                "properties": {
                    "product_id": {"type": "string", "minLength": 1},
                    "gross_cross_section_area_mm2": POS,
                    "effective_cross_sectional_area_mm2": POS,
                },
            },
        },
    },
}

OVERFLOW_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "catchment_area_m2",
        "design_rainfall_intensity_mm_per_hour",
        "eaves_gutter_length_m",
        "measure",
    ],
    "properties": {
        "catchment_area_m2": AREA,
        "design_rainfall_intensity_mm_per_hour": POS,
        "eaves_gutter_length_m": POS,
        "measure": {"type": "string", "enum": ["front_bead", "back_gap", "slots"]},
        "gradient": POS,
        "head_mm": POS,
        "average_bottom_gap_mm": POS,
        "slot_area_mm2_per_m": POS,
        "discharge_coefficient": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
        "front_bead_height_below_fascia_mm": POS,
    },
}


def _f(slope: float) -> float:
    # Table 3.4.3.2 values (integer degrees), not the former tangent formula.
    table = [
        1.00,
        1.01,
        1.02,
        1.03,
        1.03,
        1.04,
        1.05,
        1.06,
        1.07,
        1.08,
        1.09,
        1.10,
        1.11,
        1.12,
        1.12,
        1.13,
        1.14,
        1.15,
        1.16,
        1.17,
        1.18,
        1.19,
        1.20,
        1.21,
        1.22,
        1.23,
        1.24,
        1.25,
        1.27,
        1.28,
        1.29,
        1.30,
        1.31,
        1.32,
        1.34,
        1.35,
        1.36,
        1.38,
        1.39,
        1.40,
        1.42,
        1.43,
        1.45,
        1.47,
        1.48,
        1.50,
        1.52,
        1.54,
        1.56,
        1.58,
        1.60,
        1.62,
        1.64,
        1.66,
        1.69,
        1.71,
        1.74,
        1.77,
        1.80,
        1.83,
        1.87,
        1.90,
        1.94,
        1.98,
        2.03,
        2.07,
    ]
    idx = int(slope)
    return table[idx] if slope == idx else max(table[idx], table[idx + 1])


def _geometry_area(item: dict[str, Any], direction_id: str, wind_sign: float = 1.0) -> float:
    case = item["geometry"]
    if case == "flat_roof":
        return float(item["plan_area_m2"])
    if case == "single_slope_freely_exposed":
        return float(item["plan_area_m2"]) * _f(float(item["roof_slope_degrees"]))
    if case == "single_slope_partially_exposed":
        areas = _scenario_values(item, direction_id, "vertical_areas_m2", item["vertical_areas_m2"])
        delta = 0.5 * (float(areas[0]) + float(areas[1]) - float(areas[2]) - float(areas[3]))
        result = float(item["plan_area_m2"]) + (
            delta if item.get("wind_scenarios") else wind_sign * delta
        )
    elif case == "adjacent_sloping_roofs":
        first = float(
            _scenario_value(item, direction_id, "vertical_area_1_m2", item["vertical_area_1_m2"])
        )
        second = float(
            _scenario_value(item, direction_id, "vertical_area_2_m2", item["vertical_area_2_m2"])
        )
        delta = 0.5 * (second - first)
        result = (
            float(item["plan_area_1_m2"])
            + float(item["plan_area_2_m2"])
            + (delta if item.get("wind_scenarios") else wind_sign * delta)
        )
    elif case == "vertical_wall_flat_roof":
        va = _scenario_value(item, direction_id, "vertical_area_m2", item["vertical_area_m2"])
        result = float(item["plan_area_m2"]) + 0.5 * _wall_area(item, va)
    elif case == "vertical_wall_sloping_roof":
        va1 = _scenario_value(item, direction_id, "vertical_area_1_m2", item["vertical_area_1_m2"])
        va2 = _scenario_value(item, direction_id, "vertical_area_2_m2", item["vertical_area_2_m2"])
        result = float(item["plan_area_m2"]) + 0.5 * (_wall_area(item, va1) + _wall_area(item, va2))
    else:
        va1 = _scenario_value(item, direction_id, "vertical_area_1_m2", item["vertical_area_1_m2"])
        va2 = _scenario_value(item, direction_id, "vertical_area_2_m2", item["vertical_area_2_m2"])
        result = float(item["plan_area_m2"]) + 0.5 * (_wall_area(item, va1) + _wall_area(item, va2))
    if result <= 0:
        raise ValueError("calculated catchment area must be positive")
    return result


def _scenario_value(item: dict[str, Any], direction_id: str, key: str, default: Any) -> Any:
    for scenario in item.get("wind_scenarios", []):
        if scenario["direction_id"] == direction_id:
            return scenario[key]
    return default


def _scenario_values(item: dict[str, Any], direction_id: str, key: str, default: Any) -> Any:
    return _scenario_value(item, direction_id, key, default)


def _wall_area(item: dict[str, Any], value: Any) -> float:
    area = float(value)
    height = item.get("exposed_wall_height_m")
    return area if height is None else area * min(1.0, 10.0 / float(height))


def run_roof_catchment_plan(inputs: dict[str, Any]) -> dict[str, Any]:
    data = _validated(inputs, ROOF_CATCHMENT_PLAN_INPUT_SCHEMA)
    items = data["catchments"]
    sensitive = {
        "single_slope_partially_exposed",
        "adjacent_sloping_roofs",
        "vertical_wall_flat_roof",
        "vertical_wall_sloping_roof",
        "perpendicular_vertical_walls",
    }
    vector_items = [i for i in items if i["geometry"] in sensitive and i.get("wind_scenarios")]
    if vector_items:
        if any(i["geometry"] in sensitive and not i.get("wind_scenarios") for i in items):
            raise ValueError(
                "when explicit wind scenarios are supplied, every wind-sensitive component "
                "must provide direction-matched wind_scenarios"
            )
        scenario_sets = [{s["direction_id"] for s in i["wind_scenarios"]} for i in vector_items]
        if any(s != scenario_sets[0] for s in scenario_sets[1:]):
            raise ValueError(
                "wind-sensitive components must use the same wind_scenario direction_id set"
            )
        directions = sorted(scenario_sets[0])
        for i in vector_items:
            ids = [s["direction_id"] for s in i["wind_scenarios"]]
            if len(ids) != len(set(ids)):
                raise ValueError("duplicate wind_scenarios direction_id")
        signs = {direction: 1.0 for direction in directions}
    else:
        directions = ["wind_positive", "wind_negative"]
        signs = {directions[0]: 1.0, directions[1]: -1.0}

    scenario_results = []
    for direction in directions:
        grouped: dict[str, float] = defaultdict(float)
        rows = []
        for item in items:
            area = _geometry_area(item, direction, signs[direction])
            grouped[item["catchment_id"]] += area
            rows.append(
                {
                    "catchment_id": item["catchment_id"],
                    "geometry": item["geometry"],
                    "catchment_area_m2": area,
                }
            )
        scenario_results.append(
            {
                "direction_id": direction,
                "catchments": [
                    {"catchment_id": key, "catchment_area_m2": area}
                    for key, area in grouped.items()
                ],
                "total_catchment_area_m2": sum(grouped.values()),
                "components": rows,
            }
        )
    governing_by_id = []
    for catchment_id in dict.fromkeys(i["catchment_id"] for i in items):
        governing = max(
            scenario_results,
            key=lambda s: next(
                x["catchment_area_m2"] for x in s["catchments"] if x["catchment_id"] == catchment_id
            ),
        )
        governing_by_id.append(
            {
                "catchment_id": catchment_id,
                "governing_direction_id": governing["direction_id"],
                "governing_catchment_area_m2": next(
                    x["catchment_area_m2"]
                    for x in governing["catchments"]
                    if x["catchment_id"] == catchment_id
                ),
            }
        )
    governing = max(scenario_results, key=lambda s: s["total_catchment_area_m2"])
    return _result(
        "stormwater.as3500.roof_catchment_plan",
        ("3.4.3", "3.4.4"),
        {
            "wind_scenarios": scenario_results,
            "catchments": governing["catchments"],
            "total_catchment_area_m2": governing["total_catchment_area_m2"],
            "governing_direction_id": governing["direction_id"],
            "governing_by_catchment_id": governing_by_id,
        },
    )


def run_eaves_gutter_system(inputs: dict[str, Any]) -> dict[str, Any]:
    data = _validated(inputs, EAVES_SYSTEM_INPUT_SCHEMA)
    area = float(data["effective_gutter_area_mm2"])
    rain = float(data["design_rainfall_intensity_mm_per_hour"])
    gradient = float(data["gradient"])
    dpq = []
    for rating in data["manufacturer_ratings"]:
        if (
            rating["effective_gutter_area_mm2"] == area
            and rating["rainfall_intensity_mm_per_hour"] == rain
            and rating["gradient"] == gradient
        ):
            dpq.append(rating)
    if not dpq:
        raise ValueError(
            "manufacturer_ratings must contain an exact rating for the selected gutter area, "
            "design rainfall intensity, and gradient; no interpolation is applied"
        )
    rating = dpq[0]
    if len(dpq) > 1:
        raise ValueError("manufacturer_ratings contains duplicate exact ratings")
    max_area = float(rating["maximum_catchment_area_per_downpipe_m2"])
    field = "flatter_than_1:500" if gradient < 1 / 500 else "1:500_and_steeper"
    table = _select_table_352(area, gradient)
    catchments = [float(v) for v in data["downpipe_catchments_m2"]]
    count_min = ceil(sum(catchments) / max_area)
    return _result(
        "stormwater.as3500.eaves_gutter_system",
        ("3.5.2", "3.5.4", "3.5.5"),
        {
            "gradient": gradient,
            "gradient_band": field,
            "effective_gutter_area_mm2": area,
            "design_rainfall_intensity_mm_per_hour": rain,
            "manufacturer_rating_source": rating["source"],
            "maximum_catchment_area_per_downpipe_m2": max_area,
            "total_catchment_area_m2": sum(catchments),
            "minimum_downpipe_count_by_total_area": count_min,
            "downpipe_catchment_areas_m2": catchments,
            "each_downpipe_catchment_within_rating": all(x <= max_area for x in catchments),
            "table_3_5_2_selection": table,
        },
    )


def run_eaves_gutter_chart(inputs: dict[str, Any]) -> dict[str, Any]:
    """Size eaves gutter area and downpipe count from AS/NZS Figure 3.5.5."""
    data = _validated(inputs, EAVES_CHART_INPUT_SCHEMA)
    catchment = float(data["catchment_area_m2"])
    rain = float(data["design_rainfall_intensity_mm_per_hour"])
    gradient = float(data["gradient"])
    if not 50 <= rain <= 500:
        raise ValueError(
            "Figure 3.5.5 chart is bounded to its plotted design rainfall range of 50 to 500 mm/h"
        )
    downpipe_count = int(data["downpipe_count"])
    area_per_downpipe = catchment / downpipe_count
    if area_per_downpipe > 100:
        raise ValueError(
            "catchment area per downpipe must be within the Figure 3.5.5 plotted limit of 100 m2"
        )
    required_flow = area_per_downpipe * rain / 3600.0
    band = "flatter_than_1:500" if gradient < 1 / 500 else "1:500_and_steeper"
    points = _EAVES_CHART_POINTS[band]
    if required_flow < points[0][0] or required_flow > points[-1][0]:
        raise ValueError(
            "design flow must be within Figure 3.5.5 chart range "
            f"{points[0][0]} to {points[-1][0]} L/s"
        )
    if required_flow <= points[0][0]:
        chart_required_area = points[0][1]
        chart_capacity_flow = points[0][0]
    else:
        for _previous, (q1, a1) in pairwise(points):
            if required_flow <= q1:
                chart_required_area = a1
                chart_capacity_flow = q1
                break
    adopted_area = max(chart_required_area, 3500 if band == "1:500_and_steeper" else 4700)
    table = _select_table_352(adopted_area, gradient)
    max_catchment = chart_capacity_flow * 3600.0 / rain
    figure = "3.5.5(A)" if band == "1:500_and_steeper" else "3.5.5(B)"
    return _result(
        "stormwater.as3500.eaves_gutter_chart",
        ("3.5.2", "3.5.4", figure),
        {
            "method": (
                "Figure 3.5.5 dual-axis chart sizing; assumes the figure's stated gutter geometry "
                "and least-favourable downpipe/bend arrangement"
            ),
            "gradient": gradient,
            "gradient_band": band,
            "design_rainfall_intensity_mm_per_hour": rain,
            "total_catchment_area_m2": catchment,
            "downpipe_count": downpipe_count,
            "catchment_area_per_downpipe_m2": area_per_downpipe,
            "design_flow_per_downpipe_lps": required_flow,
            "total_design_flow_lps": required_flow * downpipe_count,
            "chart_required_effective_gutter_area_mm2": chart_required_area,
            "minimum_effective_gutter_area_mm2": chart_required_area,
            "adopted_effective_gutter_area_mm2_including_table_3_5_2_minimum": adopted_area,
            "chart_lookup_method": "upper flow-tick bracket; no interpolation or extrapolation",
            "chart_capacity_flow_lps_at_upper_bracket": chart_capacity_flow,
            "maximum_catchment_area_per_vertical_downpipe_m2_at_chart_bracket": max_catchment,
            "each_downpipe_catchment_within_chart_rating": area_per_downpipe <= max_catchment,
            "table_3_5_2_downpipe_selection": table,
        },
    )


def _select_table_352(area_mm2: float, gradient: float) -> dict[str, Any]:
    col = 0 if gradient >= 1 / 500 else 1
    minimum = 3500 if col == 0 else 4700
    maximum = _TABLE_352[-1][col]
    if area_mm2 < minimum or area_mm2 > maximum:
        raise ValueError(
            f"effective_gutter_area_mm2 must be in the Table 3.5.2 range {minimum} to {maximum} "
            "for the selected gradient"
        )
    row = next(row for row in _TABLE_352 if area_mm2 <= row[col])
    return {
        "listed_effective_gutter_area_mm2": row[col],
        "downpipe_size_mm": row[2],
        "downpipe_shape": row[3],
        "rectangular_or_square_size_mm": row[4],
        "table_3_5_2_row_is_rectangular_only": row[2] is None,
    }


def run_csiro_eaves_gutter(inputs: dict[str, Any]) -> dict[str, Any]:
    """Run K.G. Martin's historical 1973 CSIRO empirical eaves-gutter method."""
    data = _validated(inputs, CSIRO_EAVES_INPUT_SCHEMA)
    area_m2 = float(data["catchment_area_m2"])
    rain_mm_h = float(data["rainfall_intensity_mm_per_hour"])
    area_ft2 = area_m2 * 10.763910416709722
    rain_in_h = rain_mm_h / 25.4
    flow_load_gpm = 0.0087 * area_ft2 * rain_in_h
    flow_load_lps = flow_load_gpm * 4.54609 / 60.0
    slope = data["gutter_slope_condition"]
    x = (
        (0.4 if slope == "sloping" else 0.0)
        + _CSIRO_BEND_FACTORS[data["bend_distance_category"]][slope]
        + _CSIRO_OUTLET_FACTORS[data["outlet_position"]]
    )
    if 1 + x <= 0:
        raise ValueError("CSIRO gutter design coefficient gives a non-positive capacity factor")
    # Source equation (3), in the paper's ft2, in/hr and in2 units.
    area_in2 = (0.00757 * area_ft2 * rain_in_h / (1 + x)) ** 0.8
    multiplier = 1.10 if data["cross_section_type"] == "rectangular" else 1.0
    required_gross_mm2 = area_in2 * 645.16 * multiplier
    selected = None
    modern_table = None
    if "product_catalog" in data:
        profiles = sorted(
            (
                p
                for p in data["product_catalog"]
                if p["gross_cross_section_area_mm2"] >= required_gross_mm2
            ),
            key=lambda p: p["gross_cross_section_area_mm2"],
        )
        if not profiles:
            raise ValueError(
                "no product_catalog profile meets the CSIRO required gutter cross-sectional area"
            )
        selected = profiles[0]
        if "gradient" in data:
            modern_table = _select_table_352(
                float(selected["effective_cross_sectional_area_mm2"]), float(data["gradient"])
            )
    selected_gutter_area_mm2 = (
        float(selected["gross_cross_section_area_mm2"]) if selected else required_gross_mm2
    )
    dp_area_mm2 = selected_gutter_area_mm2 / 2.0
    return _result(
        "stormwater.as3500.csiro_eaves_gutter_research",
        ("Martin 1973 Eq. (1)–(3), Table 2",),
        {
            "method": "historical CSIRO empirical research; not current AS/NZS 3500.3 compliance",
            "catchment_area_m2": area_m2,
            "rainfall_intensity_mm_per_hour": rain_mm_h,
            "flow_load_imperial_gallons_per_minute": flow_load_gpm,
            "flow_load_lps": flow_load_lps,
            "gutter_slope_condition": slope,
            "bend_distance_category": data["bend_distance_category"],
            "outlet_position": data["outlet_position"],
            "gutter_design_coefficient_x": x,
            "required_gutter_area_in2_before_shape_adjustment": area_in2,
            "cross_section_type": data["cross_section_type"],
            "rectangular_area_multiplier": multiplier,
            "required_gross_gutter_area_mm2": required_gross_mm2,
            "selected_product": selected,
            "selected_gutter_gross_area_mm2": selected_gutter_area_mm2,
            "recommended_downpipe_cross_section_area_mm2_from_half_gutter_rule": dp_area_mm2,
            "equivalent_circular_downpipe_diameter_mm": sqrt(4 * dp_area_mm2 / 3.141592653589793),
            "table_3_5_2_downpipe_selection_for_selected_product": modern_table,
        },
    )


def run_eaves_overflow(inputs: dict[str, Any]) -> dict[str, Any]:
    data = _validated(inputs, OVERFLOW_INPUT_SCHEMA)
    qstar = (
        float(data["catchment_area_m2"])
        * float(data["design_rainfall_intensity_mm_per_hour"])
        / 3600.0
    )
    if float(data["catchment_area_m2"]) > 400:
        raise ValueError("Appendix F method scope is roof catchments up to 400 m2")
    length = float(data["eaves_gutter_length_m"])
    measure = data["measure"]
    unit_capacity = None
    detail = {}
    if measure == "front_bead":
        if float(data.get("front_bead_height_below_fascia_mm", 10)) < 10:
            raise ValueError("front bead must be at least 10 mm below fascia")
        unit_capacity = 1.5
        detail = {"capacity_basis": "Appendix F.4.4: 1.5 L/s/m"}
    elif measure == "back_gap":
        head = float(data.get("head_mm", 0))
        gap = float(data.get("average_bottom_gap_mm", 0))
        if head not in _OVERFLOW_BACK_GAP or gap not in _OVERFLOW_BACK_GAP[head]:
            raise ValueError(
                "back_gap requires Appendix F.4.2 exact tabulated head "
                "(4, 6, 8, 10, 12 mm) and average gap (1.5, 3, 4.5, 6 mm)"
            )
        unit_capacity = _OVERFLOW_BACK_GAP[head][gap]
        detail = {
            "head_mm": head,
            "average_bottom_gap_mm": gap,
            "capacity_basis": "Appendix F.4.2 Table F.1",
        }
    else:
        if "slot_area_mm2_per_m" not in data or "head_mm" not in data:
            raise ValueError("slots requires slot_area_mm2_per_m and head_mm")
        cd = float(data.get("discharge_coefficient", 0.61))
        h = float(data["head_mm"])
        # Convert Q=Cd*A*sqrt(2gh) to L/s per m for A in mm2/m and h in mm.
        # Exact dimensional coefficient is 0.001*sqrt(2*g*0.001); AS/NZS
        # prints 0.000032 inside its sqrt form, a rounded coefficient.
        exact_coefficient = 0.001 * sqrt(2 * 9.81 * 0.001)
        unit_capacity = cd * float(data["slot_area_mm2_per_m"]) * exact_coefficient * sqrt(h)
        detail = {
            "slot_area_mm2_per_m": data["slot_area_mm2_per_m"],
            "head_mm": h,
            "discharge_coefficient": cd,
            "capacity_basis": "Appendix F.4.3; Q=Cd*A*sqrt(2gh), dimensionally converted to L/s/m",
            "dimensional_coefficient_lps_per_mm2_per_sqrt_mm": exact_coefficient,
            "standard_rounded_coefficient_inside_sqrt": 0.000032,
        }
    capacity = unit_capacity * length
    margin = float(data.get("gradient", 1 / 500))
    return _result(
        "stormwater.as3500.eaves_overflow",
        ("3.5.3", "F.2", "F.3", "F.4"),
        (
            {
                "catchment_area_m2": data["catchment_area_m2"],
                "design_rainfall_intensity_mm_per_hour": data[
                    "design_rainfall_intensity_mm_per_hour"
                ],
                "design_overflow_flow_lps": qstar,
                "all_downpipes_assumed_fully_blocked": True,
                "annual_exceedance_probability_percent": 1,
                "measure": measure,
                "overflow_capacity_lps": capacity,
                "overflow_capacity_sufficient": capacity >= qstar,
                "overflow_length_m": length,
                "minimum_continuous_device_margin_mm": 3 if margin > 1 / 500 else 6,
                "unit_capacity_lps_per_m": unit_capacity,
                **detail,
            }
        ),
    )


CALCULATIONS = (
    {
        "id": "stormwater.as3500.roof_catchment_plan",
        "name": "Roof catchment plan",
        "description": (
            "Calculate grouped roof and vertical-wall catchments using AS/NZS 3500.3:2025 "
            "Clauses 3.4.3–3.4.4."
        ),
        "input_schema": ROOF_CATCHMENT_PLAN_INPUT_SCHEMA,
        "runner": run_roof_catchment_plan,
    },
    {
        "id": "stormwater.as3500.eaves_gutter_system",
        "name": "Eaves gutter and downpipe design",
        "description": (
            "Apply the Clause 3.5 workflow, a source-cited exact manufacturer rating, and "
            "Table 3.5.2 downpipe selection."
        ),
        "input_schema": EAVES_SYSTEM_INPUT_SCHEMA,
        "runner": run_eaves_gutter_system,
    },
    {
        "id": "stormwater.as3500.eaves_gutter_chart",
        "name": "Eaves gutter chart sizing",
        "description": (
            "Size minimum eaves-gutter effective area and downpipe count from bounded "
            "dual-axis data in AS/NZS 3500.3:2025 Figure 3.5.5."
        ),
        "input_schema": EAVES_CHART_INPUT_SCHEMA,
        "runner": run_eaves_gutter_chart,
    },
    {
        "id": "stormwater.as3500.csiro_eaves_gutter_research",
        "name": "CSIRO historical eaves gutter sizing",
        "description": (
            "Apply K.G. Martin's 1973 CSIRO empirical flow-load and eaves-gutter method with "
            "its published slope, bend, and outlet factors; historical research, not "
            "current-standard compliance."
        ),
        "input_schema": CSIRO_EAVES_INPUT_SCHEMA,
        "runner": run_csiro_eaves_gutter,
    },
    {
        "id": "stormwater.as3500.eaves_overflow",
        "name": "Eaves gutter overflow design",
        "description": "Check Appendix F overflow capacity against fully blocked downpipe inflow.",
        "input_schema": OVERFLOW_INPUT_SCHEMA,
        "runner": run_eaves_overflow,
    },
)
