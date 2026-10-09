"""Calculation, schema, and numerical verification tests."""

import json
import math
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from engcalcs_as3500.calculations import (
    run_design_flow,
    run_open_channel_capacity,
    run_pervious_coefficient,
    run_pumped_storage,
    run_roof_catchment,
    run_roof_flow,
    run_sag_pit_capacity,
)
from engcalcs_as3500.plugin import get_plugin
from engcalcs_as3500.schemas import OUTPUT_SCHEMA
from tests.verification_report import build_report

ROOT = Path(__file__).resolve().parents[1]


def example(filename: str) -> dict:
    return json.loads((ROOT / "examples" / filename).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("filename", "runner"),
    [
        ("roof_catchment.json", run_roof_catchment),
        ("roof_flow.json", run_roof_flow),
        ("pervious_runoff_coefficient.json", run_pervious_coefficient),
        ("surface_design_flow.json", run_design_flow),
        ("open_channel_capacity.json", run_open_channel_capacity),
        ("sag_pit_capacity.json", run_sag_pit_capacity),
        ("pumped_storage.json", run_pumped_storage),
    ],
)
def test_example_outputs_match_the_output_schema(filename, runner):
    result = runner(example(filename))
    Draft202012Validator(OUTPUT_SCHEMA).validate(result)
    assert result["standard"] == "AS/NZS 3500.3:2025"
    assert result["full_standard_compliance"] is False
    assert result["standard_compliance_evaluated"] is False


def test_independent_numerical_benchmarks_match():
    report = build_report()
    assert report["passed"]
    assert len(report["cases"]) == 10
    assert all(case["passed"] for case in report["cases"])


def test_roof_flow_uses_australian_roofed_area_coefficient():
    result = run_roof_flow(example("roof_flow.json"))["results"]
    assert result["runoff_coefficient"] == 1.0
    assert result["design_flow_lps"] == pytest.approx(50.0)


def test_roof_flow_rejects_non_australian_surface_selection():
    with pytest.raises(ValueError, match="Additional properties are not allowed"):
        run_roof_flow({**example("roof_flow.json"), "roof_surface": "steel_non_absorbent"})


def test_flat_roof_catchment_equals_plan_area():
    result = run_roof_catchment(
        {
            "plan_area_m2": 240,
            "roof_slope_degrees": 0,
            "wind_exposure": "freely_exposed",
        }
    )
    assert result["results"]["catchment_area_factor"] == 1
    assert result["results"]["catchment_area_m2"] == 240
    assert result["clauses"] == ["3.4.3.1"]


def test_single_slope_roof_factor_uses_degrees():
    result = run_roof_catchment(example("roof_catchment.json"))
    expected = 100 * (1 + 0.5 * math.tan(math.radians(30)))
    assert result["results"]["catchment_area_m2"] == pytest.approx(expected, abs=1e-12)
    assert result["clauses"] == ["3.4.3.2"]


def test_pervious_coefficient_intensity_limits_and_soil_adjustment():
    base = {
        "rainfall_10yr_60min_mm_per_hour": 10,
        "runoff_coefficient_multiplier_m": 1,
        "soil_type": "other",
    }
    lower = run_pervious_coefficient(base)["results"]
    assert lower["intensity_used_mm_per_hour"] == 25
    assert lower["runoff_coefficient"] == pytest.approx(0.0995)
    sandy = run_pervious_coefficient({**base, "soil_type": "sand"})["results"]
    assert sandy["runoff_coefficient"] == pytest.approx(0.1)
    upper = run_pervious_coefficient({**base, "rainfall_10yr_60min_mm_per_hour": 100})["results"]
    assert upper["intensity_used_mm_per_hour"] == 70


def test_pervious_coefficient_rejects_multiplier_not_in_the_standard_table():
    with pytest.raises(ValueError, match="runoff_coefficient_multiplier_m"):
        run_pervious_coefficient(
            {
                "rainfall_10yr_60min_mm_per_hour": 44.4,
                "runoff_coefficient_multiplier_m": 0.9,
                "soil_type": "other",
            }
        )


def test_trapezoidal_channel_geometry():
    result = run_open_channel_capacity(
        {
            "shape": "trapezoidal",
            "bottom_width_m": 0.4,
            "flow_depth_m": 0.2,
            "side_slope_horizontal_to_vertical": 1,
            "channel_gradient": 0.01,
            "manning_n": 0.013,
        }
    )["results"]
    assert result["flow_area_m2"] == pytest.approx(0.12)
    assert result["wetted_perimeter_m"] == pytest.approx(0.4 + 0.4 * math.sqrt(2))


def test_sag_pit_uses_common_blockage_factor_when_omitted():
    result = run_sag_pit_capacity({"inlet_perimeter_m": 4, "ponding_depth_m": 0.1})["results"]
    assert result["blockage_factor"] == 0.5


def test_sag_pit_rejects_depth_outside_clause_limit():
    with pytest.raises(ValueError, match="at most 0.12 m"):
        run_sag_pit_capacity({"inlet_perimeter_m": 4, "ponding_depth_m": 0.12001})


def test_roof_catchment_rejects_slope_beyond_table_range():
    with pytest.raises(ValueError, match="65"):
        run_roof_catchment(
            {
                "plan_area_m2": 100,
                "roof_slope_degrees": 66,
                "wind_exposure": "freely_exposed",
            }
        )


def test_roof_catchment_rejects_partially_exposed_roofs():
    with pytest.raises(ValueError, match="freely_exposed"):
        run_roof_catchment(
            {
                "plan_area_m2": 100,
                "roof_slope_degrees": 30,
                "wind_exposure": "partially_exposed",
            }
        )


def test_pumped_storage_matches_appendix_k_and_checks_wet_well_minimum():
    result = run_pumped_storage(example("pumped_storage.json"))["results"]
    assert result["storm_runoff_volume_m3"] == pytest.approx(79.92)
    assert result["pump_volume_in_30_min_m3"] == pytest.approx(54)
    assert result["minimum_wet_well_storage_m3"] == pytest.approx(10)
    assert result["required_wet_well_storage_m3"] == pytest.approx(25.92)
    assert result["storage_requirement_satisfied"] is True


def test_pumped_storage_fails_when_available_wet_well_is_too_small():
    result = run_pumped_storage(
        {**example("pumped_storage.json"), "available_wet_well_storage_m3": 9}
    )["results"]
    assert result["storage_requirement_satisfied"] is False


def test_pumped_storage_minimum_wet_well_controls_when_residual_is_smaller():
    inputs = {
        "catchment_area_m2": 1000,
        "weighted_runoff_coefficient": 0.9,
        "rainfall_10pct_120min_mm_per_hour": 44.4,
        "pump_capacity_lps": 40,
    }
    result = run_pumped_storage(inputs)["results"]
    assert result["storm_runoff_volume_m3"] == pytest.approx(79.92)
    assert result["pump_volume_in_30_min_m3"] == pytest.approx(72)
    assert result["minimum_wet_well_storage_m3"] == pytest.approx(10)
    assert result["required_wet_well_storage_m3"] == pytest.approx(10)
    assert result["required_combined_effective_storage_m3"] == pytest.approx(82)


def test_nested_non_finite_input_is_rejected():
    with pytest.raises(ValueError, match="finite numbers"):
        run_design_flow(
            {
                "design_rainfall_intensity_mm_per_hour": 100,
                "catchments": [{"area_m2": 10, "runoff_coefficient": math.nan}],
            }
        )


def test_plugin_descriptor_has_stable_ids_and_scoped_standard():
    plugin = get_plugin()
    assert plugin.id == "stormwater.as3500"
    assert plugin.source.endswith("/OpenCalcs-AS3500")
    assert plugin.calculations[0].descriptor()["jurisdiction"] == "AU"
    assert {item.standard.edition for item in plugin.calculations} == {"2025"}
    assert len({item.id for item in plugin.calculations}) == 7
