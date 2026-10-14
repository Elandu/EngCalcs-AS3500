import pytest

from opencalcs_as3500.hydraulics import (
    run_channel_capacity,
    run_channel_design,
    run_charged_pipe,
    run_pipe_capacity,
    run_pipe_design,
    run_pipe_network,
)


def test_channel_rectangular_capacity_and_normal_depth():
    base = {
        "shape": "rectangular",
        "bottom_width_m": 0.6,
        "channel_gradient": 0.01,
        "manning_n": 0.013,
        "design_flow_lps": 100,
    }
    cap = run_channel_capacity({**base, "flow_depth_m": 0.2})["results"]
    assert cap["capacity_lps"] > 100
    design = run_channel_design(base)["results"]
    assert design["normal_depth_m"] > 0
    assert design["surface_width_m"] == 0.6
    assert design["velocity_m_s"] == pytest.approx(0.1 / design["flow_area_m2"])


def test_channel_floor_clearance_and_freeboard_reported():
    r = run_channel_design(
        {
            "shape": "trapezoidal",
            "bottom_width_m": 0.4,
            "side_slope_horizontal_to_vertical": 1,
            "channel_gradient": 0.01,
            "manning_n": 0.015,
            "design_flow_lps": 50,
            "channel_bed_level_m": 0,
            "floor_or_dampcourse_level_m": 0.5,
            "minimum_freeboard_m": 0.1,
        }
    )["results"]
    assert r["surface_width_m"] > 0.4
    assert r["freeboard_satisfied"] == (r["freeboard_m"] >= 0.1)
    assert r["adjacent_floor_clearance_satisfied"] == (r["freeboard_m"] >= 0.3)


def test_asymmetric_trapezoid_and_triangular_channels():
    common = {
        "channel_gradient": 0.01,
        "manning_n": 0.015,
        "design_flow_lps": 50,
    }
    asymmetric = run_channel_capacity(
        {
            **common,
            "shape": "trapezoidal",
            "bottom_width_m": 0.4,
            "flow_depth_m": 0.25,
            "left_side_slope_horizontal_to_vertical": 1.0,
            "right_side_slope_horizontal_to_vertical": 2.0,
        }
    )["results"]
    triangle = run_channel_design(
        {
            **common,
            "shape": "triangular",
            "bottom_width_m": 0,
            "left_side_slope_horizontal_to_vertical": 1.0,
            "right_side_slope_horizontal_to_vertical": 2.0,
        }
    )["results"]
    assert asymmetric["surface_width_m"] == pytest.approx(1.15)
    assert triangle["normal_depth_m"] > 0
    assert triangle["surface_width_m"] == pytest.approx(3 * triangle["normal_depth_m"])


def test_independent_pipe_capacity_benchmarks():
    # Published independently computed full-pipe reference velocities for water at 20 C, k=0.015 mm.
    a = run_pipe_capacity(
        {
            "flow_lps": 138.89,
            "internal_diameter_mm": 300,
            "gradient": 0.01,
            "roughness_k_mm": 0.015,
            "kinematic_viscosity_m2_s": 1.004e-6,
        }
    )["results"]
    b = run_pipe_capacity(
        {
            "flow_lps": 277.78,
            "internal_diameter_mm": 450,
            "gradient": 0.005,
            "roughness_k_mm": 0.015,
            "kinematic_viscosity_m2_s": 1.004e-6,
        }
    )["results"]
    assert a["velocity_m_s"] == pytest.approx(1.9648915596, abs=1e-9)
    assert b["velocity_m_s"] == pytest.approx(1.7465702752, abs=1e-9)
    assert a["capacity_satisfied"]
    assert a["velocity_limit_satisfied"]


@pytest.mark.parametrize(
    ("diameter", "velocity", "gradient", "flow", "factor"),
    [
        (300, 1.2, 0.003560406545, 84.823001646924, 0.014548192017),
        (450, 1.4, 0.002923451654, 222.660379323177, 0.013164459411),
    ],
)
def test_independently_solved_turbulent_pipe_capacity(diameter, velocity, gradient, flow, factor):
    r = run_pipe_capacity(
        {
            "flow_lps": flow,
            "internal_diameter_mm": diameter,
            "gradient": gradient,
            "roughness_k_mm": 0.015,
            "kinematic_viscosity_m2_s": 1.004e-6,
        }
    )["results"]
    assert r["capacity_lps"] == pytest.approx(flow, abs=5e-8)
    assert r["velocity_m_s"] == pytest.approx(velocity, abs=5e-9)
    assert r["darcy_friction_factor"] == pytest.approx(factor, abs=5e-10)


def test_pipe_design_smallest_catalogued_internal_diameter():
    r = run_pipe_design(
        {
            "flow_lps": 50,
            "gradient": 0.01,
            "roughness_k_mm": 0.015,
            "kinematic_viscosity_m2_s": 1.004e-6,
            "internal_diameters_mm": [150, 225, 300],
        }
    )["results"]
    assert r["selected_internal_diameter_mm"] in (150, 225, 300)
    assert r["capacity_lps"] >= 50
    assert r["velocity_limit_satisfied"]
    assert r["velocity_m_s"] == pytest.approx(
        50 / (1000 * 3.141592653589793 * (r["selected_internal_diameter_mm"] / 1000) ** 2 / 4)
    )


def test_network_propagation_and_cycle_rejection():
    common = {
        "length_m": 10,
        "roughness_k_mm": 0.015,
        "kinematic_viscosity_m2_s": 1.004e-6,
        "internal_diameter_mm": 300,
        "pipe_gradient": 0.1,
    }
    net = {
        "nodes": [{"id": "a", "inflow_lps": 20}, {"id": "b"}, {"id": "c"}],
        "pipes": [
            {"id": "ab", "from": "a", "to": "b", **common},
            {"id": "bc", "from": "b", "to": "c", **common},
        ],
    }
    r = run_pipe_network(net)["results"]
    assert [p["flow_lps"] for p in r["pipes"]] == [20, 20]
    net["pipes"].append({"id": "ca", "from": "c", "to": "a", **common})
    with pytest.raises(ValueError, match="cycle"):
        run_pipe_network(net)


def test_charged_pipe_flow_solver_and_head_residual():
    base = {
        "length_m": 100,
        "internal_diameter_mm": 200,
        "roughness_k_mm": 0.015,
        "kinematic_viscosity_m2_s": 1.004e-6,
        "minor_loss_coefficients": [0.5, 1.0],
    }
    direct = run_charged_pipe({**base, "flow_lps": 30})["results"]
    solved = run_charged_pipe({**base, "available_head_m": direct["total_head_loss_m"]})["results"]
    assert solved["flow_lps"] == pytest.approx(30, rel=1e-9)
    assert abs(solved["head_balance_residual_m"]) < 1e-8


def test_invalid_pipe_data_rejected():
    with pytest.raises(ValueError):
        run_pipe_capacity(
            {
                "flow_lps": 1,
                "internal_diameter_mm": 100,
                "gradient": 0,
                "roughness_k_mm": 0.015,
                "kinematic_viscosity_m2_s": 1e-6,
            }
        )


def test_laminar_darcy_factor_and_capacity_inversion_residual():
    # Low velocity and high viscosity give Re=1, an exact check independent of Colebrook.
    flow_lps = 0.01 * 3.141592653589793 * 0.1**2 / 4 * 1000
    r = run_pipe_capacity(
        {
            "flow_lps": flow_lps,
            "internal_diameter_mm": 100,
            "gradient": 0.001,
            "roughness_k_mm": 0,
            "kinematic_viscosity_m2_s": 0.001,
        }
    )["results"]
    assert r["reynolds_number"] == pytest.approx(1.0)
    assert r["darcy_friction_factor"] == pytest.approx(64.0)
    assert r["capacity_satisfied"] == (flow_lps <= r["capacity_lps"])


def test_network_cover_criterion_and_disconnected_component():
    common = {
        "length_m": 10,
        "roughness_k_mm": 0.015,
        "kinematic_viscosity_m2_s": 1.004e-6,
        "internal_diameter_mm": 100,
        "pipe_gradient": 0.01,
        "surface_level_m": 10.2,
        "cover_m": 0.1,
        "required_cover_m": 0.15,
    }
    net = {
        "nodes": [
            {"id": "a", "inflow_lps": 1, "invert_level_m": 10},
            {"id": "b", "invert_level_m": 9.9},
        ],
        "pipes": [{"id": "ab", "from": "a", "to": "b", **common}],
    }
    with pytest.raises(ValueError, match="required cover"):
        run_pipe_network(net)
    net["nodes"].append({"id": "isolated", "inflow_lps": 1})
    with pytest.raises(ValueError, match="disconnected"):
        run_pipe_network(net)
