"""Independent chart-boundary review for the conservative derived envelopes."""

import pytest

from opencalcs_as3500.appendix_h_overflow_readings import lookup_overflow_reading
from opencalcs_as3500.appendix_h_roof_readings import lookup_roof_reading
from opencalcs_as3500.box_gutters import (
    run_box_gutter_design,
    run_box_side_overflow,
    run_rainhead_design,
)


@pytest.mark.parametrize(
    "figure,flow,context,lower_bound",
    [
        ("H.6a", 3, {"box_width_mm": 600}, 14),
        ("H.6b", 16, {"overflow_width_mm": 200}, 160),
        ("H.8", 16, {"box_width_mm": 300}, 137),
        ("H.4", 7, {"pipe_family": "rectangular:100x75"}, 250),
        ("H.4", 7, {"pipe_family": "circular:100"}, 235),
    ],
)
def test_envelopes_do_not_underread_independently_reviewed_chart_boundaries(
    figure, flow, context, lower_bound
):
    value, source = lookup_overflow_reading(figure, flow, context)
    assert value >= lower_bound
    assert "visual-reading allowance" in source


@pytest.mark.parametrize(
    "figure,key,maximum",
    [
        ("H.6a", "box_width_mm", 600),
        ("H.6b", "overflow_width_mm", 450),
        ("H.8", "box_width_mm", 600),
    ],
)
def test_widths_and_flows_outside_sampled_chart_bounds_are_not_extrapolated(figure, key, maximum):
    assert lookup_overflow_reading(figure, 10, {key: maximum + 1}) is None
    assert lookup_overflow_reading(figure, 16.01, {key: maximum}) is None
    assert lookup_overflow_reading(figure, 2.99, {key: maximum}) is None


def test_sump_requires_pipe_geometry_and_rejects_below_supported_family_range():
    assert lookup_overflow_reading("H.4", 16, {"pipe_area_mm2": 17671.4587}) is None
    assert lookup_overflow_reading("H.4", 9, {"pipe_family": "circular:150"}) is None
    assert lookup_overflow_reading("H.4", 16, {"pipe_family": "circular:150"})[0] >= 220


@pytest.mark.parametrize(
    "family,minimum,maximum",
    [
        ("circular:90", 3, 6),
        ("rectangular:100x75", 3, 7),
        ("circular:100", 4, 7),
        ("rectangular:100x100", 5, 9),
        ("circular:125", 6, 12),
        ("rectangular:150x100", 7, 14),
        ("rectangular:125x125", 8, 14),
        ("circular:140", 8, 14),
        ("circular:150", 10, 16),
        ("rectangular:150x150", 12, 16),
    ],
)
def test_h4_envelopes_stay_within_the_plotted_pipe_family_extent(family, minimum, maximum):
    context = {"pipe_family": family}
    assert lookup_overflow_reading("H.4", minimum, context) is not None
    assert lookup_overflow_reading("H.4", maximum, context) is not None
    assert lookup_overflow_reading("H.4", minimum - 0.01, context) is None
    assert lookup_overflow_reading("H.4", maximum + 0.01, context) is None


def test_h1_broad_envelope_retains_unadjusted_depth_and_conservative_width():
    inputs = {"design_flow_lps": 11, "box_width_mm": 500, "gradient": 0.01}
    result = run_box_gutter_design(inputs)["results"]
    assert result["minimum_depth_including_freeboard_mm"] == 175
    assert "width curve 450 mm" in result["chart_source"]
    assert "without gradient reduction" in result["chart_source"]
    assert lookup_roof_reading("H.1", 11, {"box_width_mm": 200, "gradient": 0.005}) is None


def test_h3_broad_selection_uses_actual_family_ha_and_adopted_hr():
    inputs = {
        "design_flow_lps": 16,
        "box_width_mm": 450,
        "gradient": 0.005,
        "pipe": {"shape": "circular", "diameter_mm": 150},
        "gutter_depth_at_1_in_200_mm": 140,
        "selected_depth_mm": 300,
    }
    result = run_rainhead_design(inputs)["results"]
    assert result["water_depth_mm"] == 165
    assert result["minimum_total_depth_mm"] == 276
    assert result["minimum_length_mm"] == 215
    assert "ha curve 150 mm" in result["chart_sources"][1]
    assert "hr upper bracket 300 mm" in result["chart_sources"][1]
    assert lookup_roof_reading("H.3.length", 441, {"gutter_depth_at_1_in_200_mm": 140}) is None


def test_overflow_envelopes_execute_outside_worked_examples_with_auditable_geometry():
    result = run_box_side_overflow(
        {
            "gutter_flows_lps": [6, 6],
            "box_width_mm": 500,
            "gradient": 0.005,
            "pipe": {"shape": "circular", "diameter_mm": 150},
            "overflow_width_mm": 300,
        }
    )["results"]
    assert result["chart_values_supplied_by_designer"] is False
    assert result["sump_dimension_along_gutter_mm"] == 400
    assert result["sump_transverse_dimension_mm"] == 500
    assert result["minimum_box_gutter_depth_mm"] == (
        result["offset_mm"] + result["overflow_depth_mm"] + 30
    )
