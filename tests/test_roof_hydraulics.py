import pytest

from opencalcs_as3500.roof_hydraulics import (
    run_higher_catchment,
    run_roof_spreader,
    run_standard_valley_selection,
    run_valley_gutter,
)


def test_spreader_accounts_upper_and_lower_catchments_and_sheet_capacity():
    r = run_roof_spreader(
        {
            "upper_plan_area_m2": 100,
            "lower_plan_area_m2": 200,
            "upper_roof_slope_degrees": 0,
            "lower_roof_slope_degrees": 0,
            "rainfall_intensity_mm_per_hour": 36,
            "upper_runoff_coefficient": 1,
            "lower_runoff_coefficient": 1,
            "spreader_width_m": 1,
            "sheet_depth_m": 0.01,
            "sheet_run_length_m": 1,
            "receiving_surface_slope": 0.01,
            "sheet_manning_n": 0.02,
            "spreader_drop_m": 0,
            "minor_loss_coefficient": 0,
        }
    )["results"]
    assert r["upper_flow_lps"] == pytest.approx(1)
    assert r["lower_local_flow_lps"] == pytest.approx(2)
    assert r["combined_lower_discharge_lps"] == pytest.approx(3)
    assert r["sheet_capacity_lps"] == pytest.approx(2.29035722, abs=1e-7)


def test_valley_geometry_is_derived_and_wave_allowance_is_reported():
    r = run_valley_gutter(
        {
            "left_roof_slope_degrees": 20,
            "right_roof_slope_degrees": 20,
            "plan_angle_degrees": 90,
            "bottom_width_m": 0.1,
            "flow_depth_m": 0.08,
            "channel_gradient": 0.01,
            "manning_n": 0.013,
            "design_rainfall_intensity_mm_per_hour": 100,
            "contributing_plan_area_m2": 50,
            "wave_allowance_m": 0.025,
            "freeboard_m": 0.03,
        }
    )["results"]
    assert r["left_side_slope_horizontal_to_vertical"] == pytest.approx(
        r["right_side_slope_horizontal_to_vertical"]
    )
    assert r["wave_allowance_m"] == pytest.approx(0.025)
    assert r["normal_depth_m_at_design_flow"] > 0
    assert r["critical_depth_m_at_design_flow"] > 0
    assert "not CFD equivalent" in r["limitations"]


def test_valley_requires_explicit_wave_allowance():
    data = {
        "left_roof_slope_degrees": 20,
        "right_roof_slope_degrees": 20,
        "plan_angle_degrees": 90,
        "bottom_width_m": 0.1,
        "flow_depth_m": 0.08,
        "channel_gradient": 0.01,
        "manning_n": 0.013,
        "design_rainfall_intensity_mm_per_hour": 100,
        "contributing_plan_area_m2": 50,
        "freeboard_m": 0.03,
    }
    with pytest.raises(ValueError, match="wave_allowance_m"):
        run_valley_gutter(data)


def test_higher_catchment_detail_and_combined_downstream_capacity():
    result = run_higher_catchment(
        {
            "upper_plan_area_m2": 100,
            "upper_roof_slope_degrees": 0,
            "lower_plan_area_m2": 200,
            "lower_roof_slope_degrees": 0,
            "design_rainfall_intensity_mm_per_hour": 36,
            "lower_roof_material": "corrugated_metal",
            "discharge_method": "spreader",
            "treated_width_left_mm": 1800,
            "treated_width_right_mm": 1800,
            "side_laps_sealed_full_length": True,
            "lower_gutter_capacity_lps": 4,
            "lower_downpipe_capacity_lps": 2.5,
        }
    )["results"]
    assert result["combined_lower_discharge_lps"] == pytest.approx(3)
    assert result["spreader_detail_satisfied"] is True
    assert result["lower_gutter_capacity_satisfied"] is True
    assert result["lower_downpipe_capacity_satisfied"] is False
    assert result["overflow_assessment_required"] is True


def test_standard_valley_selection_uses_inclusive_table_boundary():
    common = {
        "jurisdiction": "AU",
        "rainfall_duration_minutes": 5,
        "design_rainfall_intensity_mm_per_hour": 200,
        "catchment_area_m2": 20,
        "left_roof_slope_degrees": 20,
        "right_roof_slope_degrees": 20,
        "valley_side_angle_degrees": 16.5,
        "obstructed_below_effective_width": False,
    }
    table = run_standard_valley_selection(common)["results"]
    assert (
        table["selected_sheet_width_mm"],
        table["selected_total_gutter_depth_mm"],
        table["selected_effective_width_mm"],
    ) == (355, 47, 215)
    assert table["selected_effective_depth_mm"] == 32
    assert table["required_freeboard_mm"] == 15
    assert table["selected_total_gutter_depth_mm"] == 47


@pytest.mark.parametrize(
    ("intensity", "sheet_width", "effective_depth", "effective_width"),
    [
        (200, 355, 32, 215),
        (250, 375, 35, 234),
        (300, 395, 38, 254),
        (350, 415, 40, 273),
        (400, 435, 43, 292),
    ],
)
def test_standard_valley_table_boundaries_are_inclusive(
    intensity, sheet_width, effective_depth, effective_width
):
    result = run_standard_valley_selection(
        {
            "jurisdiction": "AU",
            "rainfall_duration_minutes": 5,
            "design_rainfall_intensity_mm_per_hour": intensity,
            "catchment_area_m2": 20,
            "left_roof_slope_degrees": 20,
            "right_roof_slope_degrees": 20,
            "valley_side_angle_degrees": 16.5,
            "obstructed_below_effective_width": False,
        }
    )["results"]
    assert result["selected_sheet_width_mm"] == sheet_width
    assert result["selected_effective_width_mm"] == effective_width
    assert result["selected_effective_depth_mm"] == effective_depth
    assert result["selected_total_gutter_depth_mm"] == effective_depth + 15


def test_standard_valley_table_rejects_intensity_above_400_mm_per_hour():
    with pytest.raises(ValueError, match="above 400 mm/h"):
        run_standard_valley_selection(
            {
                "jurisdiction": "AU",
                "rainfall_duration_minutes": 5,
                "design_rainfall_intensity_mm_per_hour": 400.01,
                "catchment_area_m2": 20,
                "left_roof_slope_degrees": 20,
                "right_roof_slope_degrees": 20,
                "valley_side_angle_degrees": 16.5,
                "obstructed_below_effective_width": False,
            }
        )


def test_standard_valley_requires_aus_five_minute_rainfall_and_nominal_angle():
    data = {
        "jurisdiction": "AU",
        "rainfall_duration_minutes": 5,
        "design_rainfall_intensity_mm_per_hour": 250,
        "catchment_area_m2": 20,
        "left_roof_slope_degrees": 40,
        "right_roof_slope_degrees": 40,
        "valley_side_angle_degrees": 16.5,
        "obstructed_below_effective_width": False,
    }
    result = run_standard_valley_selection(data)["results"]
    assert not any("35 degree" in finding for finding in result["selection_findings"])
    assert not any("12.5 degree" in finding for finding in result["selection_findings"])
    with pytest.raises(ValueError, match="rainfall_duration_minutes"):
        run_standard_valley_selection({**data, "rainfall_duration_minutes": 10})
    result = run_standard_valley_selection({**data, "valley_side_angle_degrees": 20})["results"]
    assert any("nominal 16.5 degrees" in finding for finding in result["selection_findings"])


def test_standard_valley_roof_minimum_is_12_point_5_degrees():
    data = {
        "jurisdiction": "AU",
        "rainfall_duration_minutes": 5,
        "design_rainfall_intensity_mm_per_hour": 250,
        "catchment_area_m2": 20,
        "left_roof_slope_degrees": 12.4,
        "right_roof_slope_degrees": 20,
        "valley_side_angle_degrees": 16.5,
        "obstructed_below_effective_width": False,
    }
    result = run_standard_valley_selection(data)["results"]
    assert any("12.5 degree" in finding for finding in result["selection_findings"])


def test_standard_valley_selector_rejects_out_of_range_and_obstruction():
    data = {
        "jurisdiction": "AU",
        "rainfall_duration_minutes": 5,
        "design_rainfall_intensity_mm_per_hour": 200,
        "catchment_area_m2": 41,
        "left_roof_slope_degrees": 20,
        "right_roof_slope_degrees": 20,
        "valley_side_angle_degrees": 16.5,
        "obstructed_below_effective_width": False,
    }
    with pytest.raises(ValueError, match="40 m2"):
        run_standard_valley_selection(data)

    obstructed = run_standard_valley_selection(
        {
            **data,
            "catchment_area_m2": 20,
            "obstructed_below_effective_width": True,
        }
    )["results"]
    assert obstructed["selection_satisfied"] is False
    assert any("obstructed" in finding for finding in obstructed["selection_findings"])


@pytest.mark.parametrize("area", [21, 30, 40])
def test_standard_valley_selector_rejects_unverified_large_catchment_chart(area):
    with pytest.raises(ValueError, match="axes/data need verification"):
        run_standard_valley_selection(
            {
                "jurisdiction": "AU",
                "rainfall_duration_minutes": 5,
                "design_rainfall_intensity_mm_per_hour": 250,
                "catchment_area_m2": area,
                "left_roof_slope_degrees": 20,
                "right_roof_slope_degrees": 20,
                "valley_side_angle_degrees": 16.5,
                "obstructed_below_effective_width": False,
            }
        )
