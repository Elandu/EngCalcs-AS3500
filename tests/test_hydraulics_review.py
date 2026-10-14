"""Independent closed-form checks and adverse network/energy-balance cases."""

import math

import pytest

from opencalcs_as3500.hydraulics import (
    run_charged_pipe,
    run_charged_pipe_system,
    run_pipe_capacity,
    run_pipe_design,
    run_pipe_network,
)
from opencalcs_as3500.workflows import run_pipe_network_csv


@pytest.mark.parametrize(
    "diameter,slope,k", [(0.15, 0.01, 0.000015), (0.45, 0.5, 0.000015), (0.9, 1, 0.0006)]
)
def test_capacity_against_explicit_colebrook_at_fixed_gradient(diameter, slope, k):
    # Substitute Darcy's f*V²=2gDS into Colebrook: an independent noniterative result.
    scale = math.sqrt(2 * 9.80665 * diameter * slope)
    velocity = -2 * scale * math.log10(k / (3.7 * diameter) + 2.51 * 1.004e-6 / (diameter * scale))
    expected = velocity * math.pi * diameter**2 / 4 * 1000
    output = run_pipe_capacity(
        {
            "flow_lps": 1,
            "internal_diameter_mm": diameter * 1000,
            "gradient": slope,
            "roughness_k_mm": k * 1000,
            "kinematic_viscosity_m2_s": 1.004e-6,
        }
    )["results"]
    assert output["capacity_lps"] == pytest.approx(expected, rel=1e-10)


def test_rgd_steep_pipe_example_selects_300mm_using_design_flow_velocity():
    output = run_pipe_design(
        {
            "flow_lps": 138.89,
            "gradient": 0.5,
            "roughness_k_mm": 0.015,
            "kinematic_viscosity_m2_s": 1.004e-6,
            "internal_diameters_mm": [150, 225, 300, 375, 450],
        }
    )["results"]
    assert output["selected_internal_diameter_mm"] == 300
    assert output["velocity_m_s"] == pytest.approx(1.964891560, rel=1e-8)


def test_zero_head_is_exact_zero_flow_and_energy_levels_must_agree():
    inputs = {
        "length_m": 5,
        "internal_diameter_mm": 100,
        "roughness_k_mm": 0.015,
        "kinematic_viscosity_m2_s": 1e-6,
        "minor_loss_coefficients": [],
        "available_head_m": 0,
    }
    assert run_charged_pipe(inputs)["results"]["flow_lps"] == 0
    with pytest.raises(ValueError, match="disagrees"):
        run_charged_pipe({**inputs, "upstream_level_m": 2, "downstream_level_m": 0})


def test_series_laminar_system_against_hagen_poiseuille_and_pressure_profile():
    segments = [
        {
            "id": f"p{i}",
            "length_m": length,
            "internal_diameter_mm": diameter,
            "roughness_k_mm": 0,
            "kinematic_viscosity_m2_s": 1e-6,
            "minor_loss_coefficients": [],
            "start_pipe_centre_level_m": 0,
            "end_pipe_centre_level_m": 0,
        }
        for i, (length, diameter) in enumerate([(1, 10), (2, 20)])
    ]
    head = 0.001
    resistance = sum(
        128e-6 * s["length_m"] / (9.80665 * math.pi * (s["internal_diameter_mm"] / 1000) ** 4)
        for s in segments
    )
    expected_lps = head / resistance * 1000
    result = run_charged_pipe_system(
        {"upstream_energy_level_m": 1 + head, "downstream_energy_level_m": 1, "segments": segments}
    )["results"]
    assert result["flow_lps"] == pytest.approx(expected_lps, rel=1e-10)
    assert abs(result["head_balance_residual_m"]) < 1e-12
    assert result["minimum_pressure_criterion_satisfied"] is True
    assert result["segments"][0]["end_energy_level_m"] == pytest.approx(
        result["segments"][1]["start_energy_level_m"]
    )


def network():
    return {
        "nodes": [
            {"id": "a", "inflow_lps": 1, "invert_level_m": 2},
            {"id": "b", "invert_level_m": 1},
        ],
        "pipes": [
            {
                "id": "p",
                "from": "a",
                "to": "b",
                "length_m": 10,
                "internal_diameter_mm": 150,
                "roughness_k_mm": 0.015,
                "kinematic_viscosity_m2_s": 1e-6,
            }
        ],
    }


def test_network_distinct_local_rainfall_is_conserved_and_forks_rejected():
    inputs = network()
    inputs["nodes"][0]["catchments"] = [
        {"area_m2": 100, "runoff_coefficient": 1, "rainfall_intensity_mm_per_hour": 180}
    ]
    inputs["nodes"][1]["catchments"] = [
        {"area_m2": 100, "runoff_coefficient": 0.5, "rainfall_intensity_mm_per_hour": 90}
    ]
    result = run_pipe_network(inputs)["results"]
    assert result["outlet_flows_lps"] == {"b": 7.25}
    assert result["flow_conservation_residual_lps"] == 0
    inputs["nodes"].append({"id": "c", "invert_level_m": 0.5})
    inputs["pipes"].append({**inputs["pipes"][0], "id": "p2", "to": "c"})
    with pytest.raises(ValueError, match="Bifurcations"):
        run_pipe_network(inputs)


def test_csv_network_executes_and_detects_conflicting_junctions_and_downstream_cover():
    header = (
        "pipe_id,upstream_node,downstream_node,length_m,internal_diameter_mm,"
        "upstream_invert_m,downstream_invert_m\n"
    )
    inputs = {
        "pipe_csv": header + "p1,a,b,10,150,2,1\n",
        "node_inflows_lps": {"a": 1},
        "roughness_k_mm": 0.015,
        "kinematic_viscosity_m2_s": 1e-6,
        "node_surface_levels_m": {"a": 3, "b": 2},
        "required_cover_m": 0.3,
    }
    result = run_pipe_network_csv(inputs)["results"]
    assert result["network_results"]["outlet_flows_lps"] == {"b": 1}
    inputs["node_surface_levels_m"]["b"] = 1.2
    with pytest.raises(ValueError, match="required cover"):
        run_pipe_network_csv(inputs)
    inputs["pipe_csv"] += "p2,b,c,10,150,0.9,0.8\n"
    with pytest.raises(ValueError, match="Conflicting invert"):
        run_pipe_network_csv(inputs)
