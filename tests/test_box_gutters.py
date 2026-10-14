"""Procedure arithmetic from Appendix I examples, separate from chart recovery."""

import math

import pytest

from opencalcs_as3500.box_gutters import (
    run_box_gutter_design,
    run_box_gutter_hydraulics,
    run_box_high_capacity_overflow,
    run_box_side_overflow,
    run_csiro_box_gutter,
    run_csiro_rainhead,
    run_rainhead_design,
)


def chart(figure, points, **context):
    return {
        "source": "AS/NZS 3500.3:2025 Appendix I concise worked-example reading",
        "figure": figure,
        "context": context,
        "points": points,
    }


def side_inputs():
    return {
        "gutter_flows_lps": [8, 8],
        "box_width_mm": 600,
        "gradient": 0.005,
        "pipe": {"shape": "circular", "diameter_mm": 150},
        "sump_depth_chart": chart("H.4", [[16, 220]], pipe_family="circular:150"),
        "offset_chart": chart("H.6a", [[8, 26]], box_width_mm=600),
        "overflow_width_mm": 300,
        "overflow_depth_chart": chart("H.6b", [[16, 132]], overflow_width_mm=300),
    }


def test_appendix_i1_gutter_and_rainhead_geometry():
    gutter = run_box_gutter_design(
        {
            "design_flow_lps": 15,
            "box_width_mm": 450,
            "gradient": 0.005,
            "gutter_depth_chart": chart("H.1", [[15, 140]], box_width_mm=450, gradient=0.005),
        }
    )["results"]
    assert gutter["minimum_depth_including_freeboard_mm"] == 140
    rainhead = run_rainhead_design(
        {
            "design_flow_lps": 15,
            "box_width_mm": 450,
            "gradient": 0.005,
            "pipe": {"shape": "rectangular", "width_mm": 150, "height_mm": 100},
            "gutter_depth_at_1_in_200_mm": 140,
            "water_depth_chart": chart(
                "H.3.water_depth", [[15, 144]], pipe_family="rectangular:150x100"
            ),
            "length_chart": chart("H.3.length", [[250, 185]], gutter_depth_at_1_in_200_mm=140),
            "selected_depth_mm": 250,
            "selected_length_mm": 200,
        }
    )["results"]
    # 1.67*144=240.48, rounded up to the next millimetre; published example adopts 250.
    assert rainhead["minimum_total_depth_mm"] == 241
    assert rainhead["minimum_length_mm"] == 185
    assert rainhead["selected_geometry_sufficient"]


def test_appendix_i_chart_anchors_enable_bounded_chart_free_design():
    gutter = run_box_gutter_design({"design_flow_lps": 15, "box_width_mm": 450, "gradient": 0.005})[
        "results"
    ]
    assert gutter["minimum_depth_including_freeboard_mm"] == 140
    assert gutter["chart_values_supplied_by_designer"] is False
    rainhead = run_rainhead_design(
        {
            "design_flow_lps": 15,
            "box_width_mm": 450,
            "gradient": 0.005,
            "pipe": {"shape": "rectangular", "width_mm": 150, "height_mm": 100},
            "gutter_depth_at_1_in_200_mm": 140,
            "selected_depth_mm": 250,
        }
    )["results"]
    assert rainhead["minimum_total_depth_mm"] == 241
    assert rainhead["minimum_length_mm"] == 185
    assert rainhead["rainhead_depth_used_for_length_chart_mm"] == 250


def test_appendix_i2_side_overflow_geometry():
    r = run_box_side_overflow(side_inputs())["results"]
    assert r["minimum_box_gutter_depth_mm"] == 188
    assert r["gutter_height_above_weir_mm"] == 170
    assert r["minimum_sump_width_mm"] == 400
    assert r["minimum_sump_length_mm"] == 600
    assert r["sump_dimension_along_gutter_mm"] == 400
    assert r["sump_transverse_dimension_mm"] == 600
    assert r["overflow_sole_above_gutter_sole_mm"] == pytest.approx(18.2)


def test_appendix_i2_side_overflow_chart_anchors():
    d = {
        "gutter_flows_lps": [8, 8],
        "box_width_mm": 600,
        "gradient": 0.005,
        "pipe": {"shape": "circular", "diameter_mm": 150},
        "overflow_width_mm": 300,
    }
    result = run_box_side_overflow(d)
    assert result["results"]["minimum_box_gutter_depth_mm"] == 188
    assert result["results"]["chart_values_supplied_by_designer"] is False


def test_appendix_i3_high_capacity_overflow_geometry():
    d = side_inputs()
    d.pop("overflow_width_mm")
    d.pop("overflow_depth_chart")
    d["gutter_flows_lps"] = [8.5, 6.5]
    d["direct_roof_flow_lps"] = 1
    d["offset_chart"] = chart("H.6a", [[8.5, 27]], box_width_mm=600)
    d["height_chart"] = chart("H.8", [[8.5, 83]], box_width_mm=600)
    d["free_discharge_gutter_depth_mm"] = 105
    r = run_box_high_capacity_overflow(d)["results"]
    assert r["minimum_box_gutter_depth_mm"] == 110
    assert r["minimum_sump_depth_below_datum_mm"] == 220
    assert r["sump_datum_below_gutter_sole_mm"] == 0
    d["offset_chart"] = chart("H.6a", [[8.5, 70]], box_width_mm=600)
    r = run_box_high_capacity_overflow(d)["results"]
    assert r["sump_datum_below_gutter_sole_mm"] == -10
    assert r["minimum_sump_bottom_below_gutter_sole_mm"] == 210


def test_appendix_i3_high_capacity_chart_anchors_and_h7_datum():
    d = {
        "gutter_flows_lps": [8.5, 6.5],
        "direct_roof_flow_lps": 1,
        "box_width_mm": 600,
        "gradient": 0.005,
        "pipe": {"shape": "circular", "diameter_mm": 150},
        "free_discharge_gutter_depth_mm": 105,
    }
    r = run_box_high_capacity_overflow(d)["results"]
    assert r["minimum_box_gutter_depth_mm"] == 110
    assert r["sump_datum_below_gutter_sole_mm"] == 0
    assert r["minimum_sump_bottom_below_gutter_sole_mm"] == 220
    assert r["chart_values_supplied_by_designer"] is False


def test_chart_context_bounds_and_monotonicity_are_enforced():
    d = {
        "design_flow_lps": 15,
        "box_width_mm": 450,
        "gradient": 0.005,
        "gutter_depth_chart": chart(
            "H.1", [[10, 120], [16, 145]], box_width_mm=450, gradient=0.005
        ),
    }
    assert run_box_gutter_design(d)["results"]["minimum_depth_including_freeboard_mm"] == 145
    d["gutter_depth_chart"]["context"]["box_width_mm"] = 600
    with pytest.raises(ValueError, match="context"):
        run_box_gutter_design(d)
    d["gutter_depth_chart"]["context"]["box_width_mm"] = 450
    d["design_flow_lps"] = 9
    with pytest.raises(ValueError, match="extrapolation"):
        run_box_gutter_design(d)
    d["design_flow_lps"] = 15
    d["gutter_depth_chart"]["points"] = [[10, 150], [16, 145]]
    with pytest.raises(ValueError, match="increase"):
        run_box_gutter_design(d)


def test_chart_free_design_rejects_outside_supported_chart_widths():
    with pytest.raises(ValueError, match="no supported upper-bracket reading"):
        run_box_gutter_design({"design_flow_lps": 16, "box_width_mm": 650, "gradient": 0.005})


def test_appendix_i_readings_are_upper_bracketed_and_pipe_geometry_specific():
    gutter = run_box_gutter_design({"design_flow_lps": 7, "box_width_mm": 600, "gradient": 0.005})[
        "results"
    ]
    assert gutter["minimum_depth_including_freeboard_mm"] == 105
    rainhead = run_rainhead_design(
        {
            "design_flow_lps": 14,
            "box_width_mm": 450,
            "gradient": 0.005,
            "pipe": {"shape": "rectangular", "width_mm": 150, "height_mm": 100},
            "gutter_depth_at_1_in_200_mm": 140,
            "selected_depth_mm": 250,
        }
    )["results"]
    assert rainhead["water_depth_mm"] == 144
    assert rainhead["minimum_length_mm"] == 185
    with pytest.raises(ValueError, match="below the confirmed graph range"):
        run_box_gutter_design({"design_flow_lps": 2, "box_width_mm": 600, "gradient": 0.005})
    with pytest.raises(ValueError, match="upper-bracket reading"):
        run_rainhead_design(
            {
                "design_flow_lps": 15,
                "box_width_mm": 450,
                "gradient": 0.005,
                "pipe": {"shape": "circular", "diameter_mm": 145},
                "gutter_depth_at_1_in_200_mm": 140,
                "selected_depth_mm": 250,
            }
        )


def test_h3_length_chart_uses_adopted_rainhead_depth_not_gutter_depth():
    d = {
        "design_flow_lps": 15,
        "box_width_mm": 450,
        "gradient": 0.005,
        "pipe": {"shape": "rectangular", "width_mm": 150, "height_mm": 100},
        "gutter_depth_at_1_in_200_mm": 140,
        "selected_depth_mm": 260,
        "water_depth_chart": chart(
            "H.3.water_depth", [[15, 144]], pipe_family="rectangular:150x100"
        ),
        "length_chart": chart(
            "H.3.length", [[250, 185], [260, 190]], gutter_depth_at_1_in_200_mm=140
        ),
    }
    result = run_rainhead_design(d)["results"]
    assert result["rainhead_depth_used_for_length_chart_mm"] == 260
    assert result["minimum_length_mm"] == 190


def test_box_standard_limit_and_diagnostic_are_distinct():
    d = {
        "design_flow_lps": 17,
        "box_width_mm": 450,
        "gradient": 0.005,
        "gutter_depth_chart": chart("H.1", [[17, 140]], box_width_mm=450, gradient=0.005),
    }
    with pytest.raises(ValueError, match="16 L/s"):
        run_box_gutter_design(d)
    r = run_box_gutter_hydraulics(
        {"design_flow_lps": 17, "box_width_mm": 450, "gradient": 0.005, "manning_n": 0.015}
    )["results"]
    assert r["appendix_h_design_depth_evaluated"] is False
    assert r["critical_depth_mm"] > 0
    assert r["normal_depth_mm"] > 0


def test_csiro_historical_box_gutter_method_independent_equation_check():
    d = {
        "plan_catchment_area_m2": 303,
        "rainfall_intensity_mm_per_hour": 180,
        "water_width_mm": 450,
    }
    result = run_csiro_box_gutter(d)
    r = result["results"]
    area_ft2 = 303 * 10.76391041671
    intensity_in_hr = 180 / 25.4
    width_in = 450 / 25.4
    # Independently evaluate Martin Eqs. (4)-(5) with converted inputs.
    flow_area_in2 = (0.00209 * area_ft2 * intensity_in_hr * math.sqrt(width_in)) ** (2 / 3)
    flow_gpm = 4.167 * math.sqrt(flow_area_in2**3 / width_in)
    assert r["flow_area_mm2"] == pytest.approx(flow_area_in2 * 25.4**2)
    assert r["calculated_flow_lps"] == pytest.approx(flow_gpm * (4.54609 / 60))
    assert r["water_depth_mm"] == pytest.approx(flow_area_in2 / width_in * 25.4)
    assert result["standard_compliance_evaluated"] is False


def test_csiro_rainhead_weir_and_orifice_regimes():
    weir = run_csiro_rainhead(
        {"design_flow_lps": 1, "downpipe_diameter_mm": 150, "box_side_clearance_mm": 150}
    )["results"]
    orifice = run_csiro_rainhead({"design_flow_lps": 11, "downpipe_diameter_mm": 150})["results"]
    assert weir["receiver_head_relation"] == "weir"
    assert weir["head_to_diameter_ratio"] <= 1 / 3
    assert weir["side_clearance_recommendation_satisfied"] is True
    assert orifice["receiver_head_relation"] == "orifice"
    assert orifice["head_to_diameter_ratio"] > 1 / 3
    assert orifice["estimated_receiver_depth_mm"] == pytest.approx(
        orifice["head_above_downpipe_mm"] / 0.6
    )
