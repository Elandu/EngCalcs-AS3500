"""Focused verification for expanded roof and eaves-gutter methods."""

import json
from pathlib import Path

import pytest

from opencalcs_as3500.roof_systems import (
    run_csiro_eaves_gutter,
    run_eaves_gutter_chart,
    run_eaves_gutter_system,
    run_eaves_overflow,
    run_roof_catchment_plan,
)

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_roof_catchment_independent_benchmarks():
    cases = read_json(ROOT / "validation" / "roof_systems_benchmarks.json")["cases"]
    for case in cases[:4]:
        out = run_roof_catchment_plan(case["input"])["results"]
        assert out["total_catchment_area_m2"] == pytest.approx(
            case["expected_total_catchment_area_m2"]
        )


def test_multiple_surface_components_remain_split_by_catchment():
    out = run_roof_catchment_plan(read_json(ROOT / "examples" / "roof_systems_catchments.json"))[
        "results"
    ]
    grouped = {item["catchment_id"]: item["catchment_area_m2"] for item in out["catchments"]}
    assert grouped["north_gutter"] == pytest.approx(169)
    assert grouped["south_gutter"] == pytest.approx(81)


def test_table_352_and_source_backed_rating():
    inp = read_json(ROOT / "examples" / "roof_systems_eaves_gutter.json")
    out = run_eaves_gutter_system(inp)["results"]
    assert out["minimum_downpipe_count_by_total_area"] == 4
    assert out["each_downpipe_catchment_within_rating"] is True
    assert out["table_3_5_2_selection"]["downpipe_size_mm"] == 100
    assert out["table_3_5_2_selection"]["rectangular_or_square_size_mm"] == "100x75"


def test_table_352_lower_bound_and_rectangular_only_rows():
    inp = read_json(ROOT / "examples" / "roof_systems_eaves_gutter.json")
    inp["effective_gutter_area_mm2"] = 3499
    inp["manufacturer_ratings"][0]["effective_gutter_area_mm2"] = 3499
    with pytest.raises(ValueError, match="range 3500"):
        run_eaves_gutter_system(inp)
    inp["effective_gutter_area_mm2"] = 19200
    inp["manufacturer_ratings"][0]["effective_gutter_area_mm2"] = 19200
    out = run_eaves_gutter_system(inp)["results"]["table_3_5_2_selection"]
    assert out["downpipe_size_mm"] is None
    assert out["rectangular_or_square_size_mm"] == "150x100"
    assert out["table_3_5_2_row_is_rectangular_only"] is True


def test_gutter_chart_rating_must_match_exactly():
    inp = read_json(ROOT / "examples" / "roof_systems_eaves_gutter.json")
    inp["design_rainfall_intensity_mm_per_hour"] = 146
    with pytest.raises(ValueError, match="exact rating"):
        run_eaves_gutter_system(inp)


def test_eaves_chart_sizing_matches_appendix_g_2_check():
    # Appendix G.2: 51 m2 at 145 mm/h gives 2.054 L/s and Ae=7,300 mm2.
    out = run_eaves_gutter_chart(
        {
            "catchment_area_m2": 51,
            "design_rainfall_intensity_mm_per_hour": 145,
            "gradient": 1 / 500,
            "downpipe_count": 1,
        }
    )["results"]
    assert out["design_flow_per_downpipe_lps"] == pytest.approx(2.054, abs=0.0002)
    assert out["minimum_effective_gutter_area_mm2"] == 8500
    assert out["adopted_effective_gutter_area_mm2_including_table_3_5_2_minimum"] == 8500
    assert out["maximum_catchment_area_per_vertical_downpipe_m2_at_chart_bracket"] >= 51
    assert out["each_downpipe_catchment_within_chart_rating"]


def test_eaves_chart_uses_flatter_gradient_curve_and_checks_bounds():
    inp = {
        "catchment_area_m2": 100,
        "design_rainfall_intensity_mm_per_hour": 180,
        "gradient": 1 / 1000,
        "downpipe_count": 2,
    }
    out = run_eaves_gutter_chart(inp)["results"]
    assert out["gradient_band"] == "flatter_than_1:500"
    assert out["minimum_effective_gutter_area_mm2"] > 4700
    with pytest.raises(ValueError, match="plotted design rainfall range"):
        run_eaves_gutter_chart({**inp, "design_rainfall_intensity_mm_per_hour": 501})
    with pytest.raises(ValueError, match="plotted limit of 100 m2"):
        run_eaves_gutter_chart({**inp, "catchment_area_m2": 201, "downpipe_count": 2})


def test_table_minimum_is_reported_separately_from_chart_capacity():
    out = run_eaves_gutter_chart(
        {
            "catchment_area_m2": 24.48,
            "design_rainfall_intensity_mm_per_hour": 100,
            "gradient": 1 / 500,
            "downpipe_count": 1,
        }
    )["results"]
    assert out["minimum_effective_gutter_area_mm2"] == 3000
    assert out["adopted_effective_gutter_area_mm2_including_table_3_5_2_minimum"] == 3500
    assert out["maximum_catchment_area_per_vertical_downpipe_m2_at_chart_bracket"] == pytest.approx(
        24.48
    )


def test_catchment_geometry_requires_its_measurements():
    with pytest.raises(ValueError, match="plan_area_m2"):
        run_roof_catchment_plan({"catchments": [{"catchment_id": "a", "geometry": "flat_roof"}]})


def test_catchments_share_wind_direction_before_maxima_are_selected():
    out = run_roof_catchment_plan(
        {
            "catchments": [
                {
                    "catchment_id": "shared",
                    "geometry": "adjacent_sloping_roofs",
                    "plan_area_1_m2": 50,
                    "plan_area_2_m2": 50,
                    "vertical_area_1_m2": 0,
                    "vertical_area_2_m2": 40,
                },
                {
                    "catchment_id": "shared",
                    "geometry": "adjacent_sloping_roofs",
                    "plan_area_1_m2": 50,
                    "plan_area_2_m2": 50,
                    "vertical_area_1_m2": 40,
                    "vertical_area_2_m2": 0,
                },
            ]
        }
    )["results"]
    assert [s["total_catchment_area_m2"] for s in out["wind_scenarios"]] == pytest.approx(
        [200, 200]
    )
    assert out["governing_by_catchment_id"][0]["governing_catchment_area_m2"] == pytest.approx(200)


def test_explicit_wind_scenario_vectors_preserve_global_correlation():
    def adjacent(north, south):
        return {
            "catchment_id": "shared",
            "geometry": "adjacent_sloping_roofs",
            "plan_area_1_m2": 50,
            "plan_area_2_m2": 50,
            "vertical_area_1_m2": 0,
            "vertical_area_2_m2": 0,
            "wind_scenarios": [
                {"direction_id": "north", "vertical_area_1_m2": 0, "vertical_area_2_m2": north},
                {"direction_id": "south", "vertical_area_1_m2": 0, "vertical_area_2_m2": south},
            ],
        }

    out = run_roof_catchment_plan({"catchments": [adjacent(40, 10), adjacent(10, 40)]})["results"]
    assert [s["total_catchment_area_m2"] for s in out["wind_scenarios"]] == pytest.approx(
        [225, 225]
    )
    assert out["total_catchment_area_m2"] == pytest.approx(225)


def test_mixed_explicit_and_implicit_sensitive_wind_vectors_are_rejected():
    base = {
        "catchment_id": "a",
        "geometry": "adjacent_sloping_roofs",
        "plan_area_1_m2": 10,
        "plan_area_2_m2": 10,
        "vertical_area_1_m2": 0,
        "vertical_area_2_m2": 10,
    }
    vector = {
        **base,
        "wind_scenarios": [
            {"direction_id": "north", "vertical_area_1_m2": 0, "vertical_area_2_m2": 10}
        ],
    }
    with pytest.raises(ValueError, match="every wind-sensitive"):
        run_roof_catchment_plan({"catchments": [base, vector]})


def test_overflow_fully_blocked_front_bead_benchmark():
    case = read_json(ROOT / "validation" / "roof_systems_benchmarks.json")["cases"][4]
    out = run_eaves_overflow(case["input"])["results"]
    assert out["design_overflow_flow_lps"] == pytest.approx(
        case["expected_design_overflow_flow_lps"]
    )
    assert out["overflow_capacity_lps"] == pytest.approx(case["expected_overflow_capacity_lps"])
    assert out["all_downpipes_assumed_fully_blocked"] is True
    assert out["overflow_capacity_sufficient"]


def test_overflow_back_gap_uses_exact_table_value():
    case = read_json(ROOT / "validation" / "roof_systems_benchmarks.json")["cases"][5]
    out = run_eaves_overflow(case["input"])["results"]
    assert out["overflow_capacity_lps"] == pytest.approx(case["expected_overflow_capacity_lps"])
    case["input"]["head_mm"] = 9
    with pytest.raises(ValueError, match="exact tabulated"):
        run_eaves_overflow(case["input"])


@pytest.mark.parametrize("area", [400.01, 0])
def test_overflow_area_bounds(area):
    inp = {
        "catchment_area_m2": area,
        "design_rainfall_intensity_mm_per_hour": 100,
        "eaves_gutter_length_m": 1,
        "measure": "front_bead",
    }
    if area == 0:
        with pytest.raises(ValueError):
            run_eaves_overflow(inp)
    else:
        with pytest.raises(ValueError, match="up to 400 m2"):
            run_eaves_overflow(inp)


def test_overflow_rejects_front_bead_too_high():
    inp = {
        "catchment_area_m2": 10,
        "design_rainfall_intensity_mm_per_hour": 100,
        "eaves_gutter_length_m": 1,
        "measure": "front_bead",
        "front_bead_height_below_fascia_mm": 9,
    }
    with pytest.raises(ValueError, match="at least 10 mm"):
        run_eaves_overflow(inp)


def test_slot_capacity_uses_independently_derived_units():
    from math import sqrt

    inp = {
        "catchment_area_m2": 20,
        "design_rainfall_intensity_mm_per_hour": 100,
        "eaves_gutter_length_m": 4,
        "measure": "slots",
        "head_mm": 10,
        "slot_area_mm2_per_m": 1000,
        "discharge_coefficient": 0.61,
    }
    result = run_eaves_overflow(inp)["results"]
    expected = 0.61 * 1000 * 0.001 * sqrt(2 * 9.81 * 0.001 * 10)
    assert result["unit_capacity_lps_per_m"] == pytest.approx(expected)
    assert result["dimensional_coefficient_lps_per_mm2_per_sqrt_mm"] == pytest.approx(
        0.001 * sqrt(2 * 9.81 * 0.001)
    )


def test_historical_csiro_eaves_gutter_source_benchmark():
    inp = read_json(ROOT / "examples" / "roof_systems_csiro_eaves.json")
    result = run_csiro_eaves_gutter(inp)["results"]
    assert result["gutter_design_coefficient_x"] == pytest.approx(1.275)
    assert result["flow_load_imperial_gallons_per_minute"] == pytest.approx(66.363321703, abs=1e-9)
    assert result["required_gutter_area_in2_before_shape_adjustment"] == pytest.approx(
        13.2928674232, abs=1e-9
    )
    assert result["selected_product"]["product_id"] == "rounded_quad_10k"
    assert result[
        "recommended_downpipe_cross_section_area_mm2_from_half_gutter_rule"
    ] == pytest.approx(5000)
    assert result["table_3_5_2_downpipe_selection_for_selected_product"]["downpipe_size_mm"] == 125
    assert "not current AS/NZS" in result["method"]


def test_csiro_rectangular_area_allowance_and_schema_rejection():
    inp = read_json(ROOT / "examples" / "roof_systems_csiro_eaves.json")
    inp["cross_section_type"] = "rectangular"
    out = run_csiro_eaves_gutter(inp)["results"]
    assert out["rectangular_area_multiplier"] == 1.1
    assert out["required_gross_gutter_area_mm2"] == pytest.approx(
        out["required_gutter_area_in2_before_shape_adjustment"] * 645.16 * 1.1
    )
    with pytest.raises(ValueError, match="bend_distance_category"):
        run_csiro_eaves_gutter({k: v for k, v in inp.items() if k != "bend_distance_category"})
