from math import exp

import pytest

from opencalcs_as3500.storage_routing import (
    run_detention_routing,
    run_detention_storage_sizing,
    run_orifice_capacity,
    run_weir_capacity,
)


def test_orifice_and_weir_hand_calculations():
    q = run_orifice_capacity({"opening_area_m2": 0.01, "discharge_coefficient": 0.62, "head_m": 1})[
        "results"
    ]["capacity_lps"]
    assert q == pytest.approx(27.47, rel=0.002)
    w = run_weir_capacity({"crest_length_m": 1, "discharge_coefficient": 1.7, "head_m": 0.25})[
        "results"
    ]["capacity_lps"]
    assert w == pytest.approx(212.5)


def test_submerged_orifice_requires_coefficient_and_uses_differential_head():
    data = {
        "opening_area_m2": 0.01,
        "discharge_coefficient": 0.62,
        "head_m": 1,
        "tailwater_depth_m": 0.4,
    }
    with pytest.raises(ValueError, match="submerged_discharge_coefficient"):
        run_orifice_capacity(data)
    data["submerged_discharge_coefficient"] = 0.58
    assert run_orifice_capacity(data)["results"]["effective_head_m"] == pytest.approx(0.6)


def test_submerged_weir_uses_explicit_empirical_coefficient_convention():
    with pytest.raises(ValueError, match="submerged_discharge_coefficient"):
        run_weir_capacity(
            {
                "crest_length_m": 1,
                "discharge_coefficient": 1.7,
                "head_m": 1,
                "tailwater_depth_m": 0.4,
            }
        )
    result = run_weir_capacity(
        {
            "crest_length_m": 1,
            "discharge_coefficient": 1.7,
            "head_m": 1,
            "tailwater_depth_m": 0.4,
            "submerged_discharge_coefficient": 0.8,
        }
    )["results"]
    assert result["capacity_lps"] == pytest.approx(0.8 * 0.6**1.5 * 1000)
    assert result["flow_condition"] == "submerged_differential_head_assumption"
    assert "not a universal drowned-weir law" in result["hydraulic_applicability"]


def test_submerged_routing_weir_requires_its_own_coefficient():
    data = {
        "stage_storage": [
            {"stage_m": 0, "storage_m3": 0},
            {"stage_m": 1, "storage_m3": 100},
        ],
        "hyetograph": [{"duration_s": 10, "rainfall_intensity_mm_per_hour": 0}],
        "catchment_area_m2": 100,
        "runoff_coefficient": 1,
        "loss_rate_mm_per_hour": 0,
        "outlet": {
            "type": "weir",
            "coefficient": 1.7,
            "length_m": 1,
            "crest_stage_m": 0,
            "tailwater_stage_m": 0.2,
        },
        "allowable_discharge_lps": 100,
        "initial_stage_m": 0.5,
    }
    with pytest.raises(ValueError, match="submerged_coefficient"):
        run_detention_routing(data)


def test_modified_puls_constant_inflow_and_constant_outflow_is_mass_conserving():
    data = {
        "stage_storage": [{"stage_m": 0, "storage_m3": 0}, {"stage_m": 1, "storage_m3": 100}],
        "stage_discharge": [
            {"stage_m": 0, "discharge_lps": 10},
            {"stage_m": 1, "discharge_lps": 10},
        ],
        "hyetograph": [{"duration_s": 100, "rainfall_intensity_mm_per_hour": 360}],
        "catchment_area_m2": 1000,
        "runoff_coefficient": 1,
        "loss_rate_mm_per_hour": 0,
        "outlet": {"type": "weir", "coefficient": 1.7, "length_m": 1},
        "allowable_discharge_lps": 5,
        "duration_step_s": 10,
    }
    r = run_detention_routing(data)["results"]
    assert r["peak_storage_m3"] == pytest.approx(9.05, abs=1e-8)
    assert r["mass_balance_error_m3"] == pytest.approx(0, abs=1e-8)
    assert len(r["hydrograph"]) == 10
    assert r["peak_total_site_discharge_lps"] == pytest.approx(10)
    assert r["allowable_discharge_satisfied"] is False
    controlled = run_detention_routing({**data, "flow_control_limit_lps": 5})["results"]
    assert controlled["peak_total_site_discharge_lps"] == pytest.approx(5)
    assert controlled["allowable_discharge_satisfied"] is True


def test_routing_rejects_nonmonotone_curves_and_unmodelled_overflow():
    base = {
        "stage_storage": [{"stage_m": 0, "storage_m3": 0}, {"stage_m": 1, "storage_m3": 1}],
        "hyetograph": [{"duration_s": 20, "rainfall_intensity_mm_per_hour": 360}],
        "stage_discharge": [
            {"stage_m": 0, "discharge_lps": 0},
            {"stage_m": 1, "discharge_lps": 0},
        ],
        "catchment_area_m2": 1000,
        "runoff_coefficient": 1,
        "loss_rate_mm_per_hour": 0,
        "outlet": {"type": "weir", "coefficient": 1.7, "length_m": 1},
        "allowable_discharge_lps": 0,
    }
    with pytest.raises(ValueError, match="strictly increasing"):
        run_detention_routing(
            {
                **base,
                "stage_storage": [{"stage_m": 0, "storage_m3": 0}, {"stage_m": 0, "storage_m3": 1}],
            }
        )
    with pytest.raises(ValueError, match="storage_m3 values must be strictly increasing"):
        run_detention_routing(
            {
                **base,
                "stage_storage": [
                    {"stage_m": 0, "storage_m3": 0},
                    {"stage_m": 0.5, "storage_m3": 1},
                    {"stage_m": 1, "storage_m3": 1},
                ],
            }
        )
    with pytest.raises(ValueError, match="stage-storage curve range"):
        run_detention_routing(base)


def test_constant_area_tank_and_stage_discharge_curve_are_supported():
    result = run_detention_routing(
        {
            "tank_plan_area_m2": 10,
            "tank_bottom_stage_m": 0,
            "tank_top_stage_m": 2,
            "stage_discharge": [
                {"stage_m": 0, "discharge_lps": 0},
                {"stage_m": 2, "discharge_lps": 0},
            ],
            "hyetograph": [{"duration_s": 10, "rainfall_intensity_mm_per_hour": 360}],
            "catchment_area_m2": 1000,
            "runoff_coefficient": 1,
            "loss_rate_mm_per_hour": 0,
            "allowable_discharge_lps": 0,
            "duration_step_s": 10,
        }
    )["results"]
    assert result["peak_storage_m3"] == pytest.approx(1)
    assert result["mass_balance_error_m3"] == pytest.approx(0, abs=1e-8)


def test_detention_sizing_finds_nine_cubic_metres_and_conserves_mass():
    base = {
        "hyetographs": [
            {
                "name": "constant 1 L/s",
                "hyetograph": [{"duration_s": 9000, "rainfall_intensity_mm_per_hour": 1}],
            }
        ],
        "catchment_area_m2": 3600,
        "runoff_coefficient": 1,
        "loss_rate_mm_per_hour": 0,
        "allowable_discharge_lps": 0,
        "tank_bottom_stage_m": 0,
        "tank_depth_m": 1,
        "freeboard_m": 0,
        "stage_discharge": [{"stage_m": 0, "discharge_lps": 0}, {"stage_m": 1, "discharge_lps": 0}],
        "duration_step_s": 60,
        "area_tolerance_m2": 1e-4,
    }
    result = run_detention_storage_sizing(base)["results"]
    assert result["minimum_plan_area_m2"] == pytest.approx(9, abs=1e-4)
    event = result["event_results"][0]
    assert event["storage_satisfied"] is True
    assert event["mass_balance_error_m3"] == pytest.approx(0, abs=1e-8)


def test_detention_sizing_is_stable_under_timestep_refinement():
    base = {
        "hyetographs": [
            {
                "name": "short pulse",
                "hyetograph": [{"duration_s": 600, "rainfall_intensity_mm_per_hour": 10}],
            }
        ],
        "catchment_area_m2": 3600,
        "runoff_coefficient": 1,
        "loss_rate_mm_per_hour": 0,
        "allowable_discharge_lps": 0,
        "tank_bottom_stage_m": 0,
        "tank_depth_m": 1,
        "freeboard_m": 0,
        "stage_discharge": [{"stage_m": 0, "discharge_lps": 0}, {"stage_m": 1, "discharge_lps": 0}],
        "area_tolerance_m2": 1e-3,
    }
    coarse = run_detention_storage_sizing({**base, "duration_step_s": 30})["results"][
        "minimum_plan_area_m2"
    ]
    fine = run_detention_storage_sizing({**base, "duration_step_s": 10})["results"][
        "minimum_plan_area_m2"
    ]
    assert coarse == pytest.approx(fine, abs=1e-3)


@pytest.mark.parametrize(
    "blocks",
    [
        [
            {"duration_s": 10, "rainfall_intensity_mm_per_hour": 0},
            {"duration_s": 10, "rainfall_intensity_mm_per_hour": 2},
        ],
        [
            {"duration_s": 10, "rainfall_intensity_mm_per_hour": 2},
            {"duration_s": 10, "rainfall_intensity_mm_per_hour": 0},
        ],
    ],
)
def test_constant_rainfall_blocks_preserve_input_volume_independent_of_step(blocks):
    base = {
        "stage_storage": [{"stage_m": 0, "storage_m3": 0}, {"stage_m": 10, "storage_m3": 100}],
        "stage_discharge": [
            {"stage_m": 0, "discharge_lps": 0},
            {"stage_m": 10, "discharge_lps": 0},
        ],
        "hyetograph": blocks,
        "catchment_area_m2": 3600,
        "runoff_coefficient": 1,
        "loss_rate_mm_per_hour": 0,
        "allowable_discharge_lps": 1,
    }
    for step in (2, 5, 10):
        result = run_detention_routing({**base, "duration_step_s": step})["results"]
        assert result["total_controlled_inflow_m3"] == pytest.approx(0.02)
        assert result["total_rainfall_inflow_m3"] == pytest.approx(0.02)
        assert sum(
            point["rainfall_inflow_lps"] * point["duration_s"] / 1000
            for point in result["hydrograph"]
        ) == pytest.approx(0.02)
        assert result["peak_storage_m3"] == pytest.approx(0.02)
        assert result["mass_balance_error_m3"] == pytest.approx(0, abs=1e-10)


def test_initially_wet_tank_drainage_is_volume_limited_without_psd_throttling():
    result = run_detention_routing(
        {
            "stage_storage": [{"stage_m": 0, "storage_m3": 0}, {"stage_m": 1, "storage_m3": 1}],
            "stage_discharge": [
                {"stage_m": 0, "discharge_lps": 0},
                {"stage_m": 1, "discharge_lps": 1000},
            ],
            "hyetograph": [{"duration_s": 10, "rainfall_intensity_mm_per_hour": 0}],
            "catchment_area_m2": 1,
            "runoff_coefficient": 1,
            "loss_rate_mm_per_hour": 0,
            "allowable_discharge_lps": 10,
            "initial_stage_m": 1,
            "duration_step_s": 10,
        }
    )["results"]
    step = result["hydrograph"][0]
    assert result["peak_storage_m3"] == pytest.approx(1)
    assert result["peak_storage_time_s"] == 0
    assert step["storage_m3"] == pytest.approx(0)
    assert step["volume_limited_at_dry_boundary"] is True
    assert step["interval_average_outlet_lps"] == pytest.approx(100)
    assert result["total_volume_limited_discharge_correction_m3"] == pytest.approx(4)
    assert result["mass_balance_error_m3"] == pytest.approx(0, abs=1e-10)
    assert result["peak_total_site_discharge_lps"] == pytest.approx(1000)
    assert result["allowable_discharge_satisfied"] is False


def test_linear_reservoir_routing_refines_toward_analytic_solution():
    base = {
        "stage_storage": [{"stage_m": 0, "storage_m3": 0}, {"stage_m": 1, "storage_m3": 1}],
        "stage_discharge": [
            {"stage_m": 0, "discharge_lps": 0},
            {"stage_m": 1, "discharge_lps": 100},
        ],
        "hyetograph": [{"duration_s": 10, "rainfall_intensity_mm_per_hour": 0}],
        "catchment_area_m2": 1,
        "runoff_coefficient": 1,
        "loss_rate_mm_per_hour": 0,
        "allowable_discharge_lps": 1000,
        "initial_stage_m": 1,
    }
    exact = exp(-1)
    coarse = run_detention_routing({**base, "duration_step_s": 10})["results"]["hydrograph"][-1][
        "storage_m3"
    ]
    fine = run_detention_routing({**base, "duration_step_s": 1})["results"]["hydrograph"][-1][
        "storage_m3"
    ]
    assert abs(fine - exact) < abs(coarse - exact)


def test_routing_bounds_step_count():
    route = {
        "stage_storage": [{"stage_m": 0, "storage_m3": 0}, {"stage_m": 1, "storage_m3": 1}],
        "stage_discharge": [{"stage_m": 0, "discharge_lps": 0}, {"stage_m": 1, "discharge_lps": 0}],
        "hyetograph": [{"duration_s": 100001, "rainfall_intensity_mm_per_hour": 0}],
        "catchment_area_m2": 1,
        "runoff_coefficient": 1,
        "loss_rate_mm_per_hour": 0,
        "allowable_discharge_lps": 0,
        "duration_step_s": 1,
    }
    with pytest.raises(ValueError, match="100000-step limit"):
        run_detention_routing(route)


def test_sizing_rejects_duplicate_event_names():
    data = {
        "hyetographs": [
            {
                "name": "same",
                "hyetograph": [{"duration_s": 1, "rainfall_intensity_mm_per_hour": 0}],
            },
            {
                "name": "same",
                "hyetograph": [{"duration_s": 1, "rainfall_intensity_mm_per_hour": 0}],
            },
        ],
        "catchment_area_m2": 1,
        "runoff_coefficient": 1,
        "loss_rate_mm_per_hour": 0,
        "allowable_discharge_lps": 0,
        "tank_bottom_stage_m": 0,
        "tank_depth_m": 1,
        "freeboard_m": 0,
        "stage_discharge": [{"stage_m": 0, "discharge_lps": 0}, {"stage_m": 1, "discharge_lps": 0}],
    }
    with pytest.raises(ValueError, match="event names must be unique"):
        run_detention_storage_sizing(data)


def test_allowable_discharge_assessment_includes_bypass_and_overflow():
    result = run_detention_routing(
        {
            "stage_storage": [{"stage_m": 0, "storage_m3": 0}, {"stage_m": 1, "storage_m3": 1}],
            "stage_discharge": [
                {"stage_m": 0, "discharge_lps": 0},
                {"stage_m": 1, "discharge_lps": 0},
            ],
            "hyetograph": [{"duration_s": 10, "rainfall_intensity_mm_per_hour": 10}],
            "catchment_area_m2": 3600,
            "runoff_coefficient": 1,
            "loss_rate_mm_per_hour": 0,
            "bypass_fraction": 0.5,
            "allowable_discharge_lps": 6,
            "overflow_stage_m": 0,
            "overflow_coefficient": 0.2,
            "overflow_length_m": 1,
            "duration_step_s": 10,
        }
    )["results"]
    assert result["hydrograph"][0]["bypass_lps"] == pytest.approx(5)
    assert result["peak_total_site_discharge_lps"] > 6
    assert result["allowable_discharge_satisfied"] is False


def test_peak_site_discharge_includes_old_outflow_and_new_block_bypass():
    result = run_detention_routing(
        {
            "stage_storage": [
                {"stage_m": 0, "storage_m3": 0},
                {"stage_m": 1, "storage_m3": 100},
            ],
            "stage_discharge": [
                {"stage_m": 0, "discharge_lps": 0},
                {"stage_m": 1, "discharge_lps": 1000},
            ],
            "hyetograph": [
                {"duration_s": 1, "rainfall_intensity_mm_per_hour": 0},
                {"duration_s": 10, "rainfall_intensity_mm_per_hour": 100},
            ],
            "catchment_area_m2": 3600,
            "runoff_coefficient": 1,
            "loss_rate_mm_per_hour": 0,
            "bypass_fraction": 0.99,
            "allowable_discharge_lps": 2000,
            "initial_stage_m": 1,
            "duration_step_s": 1,
        }
    )["results"]
    boundary = result["hydrograph"][1]
    previous_outflow = result["hydrograph"][0]["outlet_lps"]
    expected_boundary = previous_outflow + boundary["bypass_lps"]
    assert boundary["site_discharge_peak_estimate_lps"] == pytest.approx(expected_boundary)
    assert expected_boundary > result["hydrograph"][0]["site_discharge_peak_estimate_lps"]
    assert result["peak_storage_time_s"] == 0
    assert result["peak_total_site_discharge_lps"] == pytest.approx(
        max(point["site_discharge_peak_estimate_lps"] for point in result["hydrograph"])
    )
