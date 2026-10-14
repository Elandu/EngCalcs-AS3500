# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded pipe and open-channel hydraulics for stormwater design."""

from collections import defaultdict, deque
from collections.abc import Mapping
from copy import deepcopy
from math import log10, pi, sqrt
from typing import Any

from opencalcs_as3500.calculations import _result, _validated

POS = {"type": "number", "exclusiveMinimum": 0}
NN = {"type": "number", "minimum": 0}

CHANNEL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "shape",
        "bottom_width_m",
        "channel_gradient",
        "manning_n",
        "flow_depth_m",
        "design_flow_lps",
    ],
    "properties": {
        "shape": {"enum": ["rectangular", "trapezoidal", "triangular"]},
        "bottom_width_m": NN,
        "channel_gradient": POS,
        "manning_n": POS,
        "design_flow_lps": POS,
        "side_slope_horizontal_to_vertical": NN,
        "left_side_slope_horizontal_to_vertical": NN,
        "right_side_slope_horizontal_to_vertical": NN,
        "flow_depth_m": POS,
        "max_depth_m": POS,
        "floor_or_dampcourse_level_m": {"type": "number"},
        "channel_bed_level_m": {"type": "number"},
        "minimum_freeboard_m": NN,
    },
    "allOf": [
        {
            "if": {"properties": {"shape": {"enum": ["rectangular", "trapezoidal"]}}},
            "then": {"properties": {"bottom_width_m": POS}},
        },
        {
            "if": {"properties": {"shape": {"const": "trapezoidal"}}},
            "then": {
                "anyOf": [
                    {
                        "required": ["side_slope_horizontal_to_vertical"],
                        "properties": {"side_slope_horizontal_to_vertical": POS},
                    },
                    {
                        "required": [
                            "left_side_slope_horizontal_to_vertical",
                            "right_side_slope_horizontal_to_vertical",
                        ],
                        "properties": {
                            "left_side_slope_horizontal_to_vertical": POS,
                            "right_side_slope_horizontal_to_vertical": POS,
                        },
                    },
                ]
            },
        },
        {
            "if": {"properties": {"shape": {"const": "triangular"}}},
            "then": {
                "required": [
                    "left_side_slope_horizontal_to_vertical",
                    "right_side_slope_horizontal_to_vertical",
                ],
                "properties": {
                    "bottom_width_m": {"const": 0},
                    "left_side_slope_horizontal_to_vertical": POS,
                    "right_side_slope_horizontal_to_vertical": POS,
                },
            },
        },
    ],
}
CHANNEL_DESIGN_SCHEMA = {
    **CHANNEL_SCHEMA,
    "required": ["shape", "bottom_width_m", "channel_gradient", "manning_n", "design_flow_lps"],
}
PIPE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "flow_lps",
        "internal_diameter_mm",
        "gradient",
        "roughness_k_mm",
        "kinematic_viscosity_m2_s",
    ],
    "properties": {
        "flow_lps": NN,
        "internal_diameter_mm": POS,
        "gradient": POS,
        "roughness_k_mm": NN,
        "kinematic_viscosity_m2_s": POS,
        "max_velocity_m_s": POS,
        "outlet_recommended_velocity_m_s": POS,
    },
}
PIPE_DESIGN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "flow_lps",
        "gradient",
        "roughness_k_mm",
        "kinematic_viscosity_m2_s",
        "internal_diameters_mm",
    ],
    "properties": {
        "flow_lps": POS,
        "gradient": POS,
        "roughness_k_mm": NN,
        "kinematic_viscosity_m2_s": POS,
        "internal_diameters_mm": {
            "type": "array",
            "minItems": 1,
            "items": POS,
            "uniqueItems": True,
        },
        "max_velocity_m_s": POS,
        "outlet_recommended_velocity_m_s": POS,
    },
}
NETWORK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["nodes", "pipes"],
    "properties": {
        "nodes": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "inflow_lps": NN,
                    "catchments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "area_m2",
                                "runoff_coefficient",
                                "rainfall_intensity_mm_per_hour",
                            ],
                            "properties": {
                                "area_m2": POS,
                                "runoff_coefficient": {
                                    "type": "number",
                                    "minimum": 0,
                                    "maximum": 1,
                                },
                                "rainfall_intensity_mm_per_hour": POS,
                            },
                        },
                    },
                    "invert_level_m": {"type": "number"},
                },
            },
        },
        "pipes": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id",
                    "from",
                    "to",
                    "length_m",
                    "internal_diameter_mm",
                    "roughness_k_mm",
                    "kinematic_viscosity_m2_s",
                ],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "length_m": POS,
                    "internal_diameter_mm": POS,
                    "roughness_k_mm": NN,
                    "kinematic_viscosity_m2_s": POS,
                    "cover_m": NN,
                    "required_cover_m": NN,
                    "surface_level_m": {"type": "number"},
                    "downstream_surface_level_m": {"type": "number"},
                    "pipe_gradient": POS,
                    "maximum_velocity_m_s": POS,
                    "outlet_recommended_velocity_m_s": POS,
                    "outlet": {"type": "boolean"},
                },
            },
        },
    },
}
CHARGED_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "length_m",
        "internal_diameter_mm",
        "roughness_k_mm",
        "kinematic_viscosity_m2_s",
        "minor_loss_coefficients",
    ],
    "properties": {
        "length_m": POS,
        "internal_diameter_mm": POS,
        "roughness_k_mm": NN,
        "kinematic_viscosity_m2_s": POS,
        "minor_loss_coefficients": {"type": "array", "items": NN},
        "flow_lps": NN,
        "available_head_m": NN,
        "upstream_level_m": {"type": "number"},
        "downstream_level_m": {"type": "number"},
    },
    "oneOf": [{"required": ["flow_lps"]}, {"required": ["available_head_m"]}],
    "allOf": [
        {
            "if": {
                "anyOf": [{"required": ["upstream_level_m"]}, {"required": ["downstream_level_m"]}]
            },
            "then": {"required": ["upstream_level_m", "downstream_level_m"]},
        }
    ],
}


def _manning(
    depth: float, width: float, side: float, slope: float, n: float, side_right: float | None = None
) -> tuple[float, float, float, float]:
    right = side if side_right is None else side_right
    area = depth * (width + 0.5 * (side + right) * depth)
    perimeter = width + depth * sqrt(1 + side * side) + depth * sqrt(1 + right * right)
    radius = area / perimeter
    flow = area * radius ** (2 / 3) * sqrt(slope) / n
    top = width + (side + right) * depth
    return flow, area, perimeter, top


def _channel_sides(data: Mapping[str, Any]) -> tuple[float, float]:
    if data["shape"] == "rectangular":
        return 0.0, 0.0
    legacy = data.get("side_slope_horizontal_to_vertical")
    left = data.get("left_side_slope_horizontal_to_vertical", legacy)
    right = data.get("right_side_slope_horizontal_to_vertical", legacy)
    return float(left), float(right)


def _channel(data: Mapping[str, Any], ident: str) -> dict[str, Any]:
    side, side_right = _channel_sides(data)
    width, slope, n, q = (
        float(data[k])
        for k in ("bottom_width_m", "channel_gradient", "manning_n", "design_flow_lps")
    )
    lo, hi = 0.0, float(data.get("max_depth_m", 10.0))
    if _manning(hi, width, side, slope, n, side_right)[0] < q / 1000:
        raise ValueError("required depth exceeds max_depth_m or 10 m search bound")
    for _ in range(100):
        mid = (lo + hi) / 2
        if _manning(mid, width, side, slope, n, side_right)[0] < q / 1000:
            lo = mid
        else:
            hi = mid
    depth = (lo + hi) / 2
    flow, area, perimeter, top = _manning(depth, width, side, slope, n, side_right)
    bed = data.get("channel_bed_level_m")
    floor = data.get("floor_or_dampcourse_level_m")
    clearance = None if bed is None or floor is None else float(floor) - float(bed) - depth
    needed = float(data.get("minimum_freeboard_m", 0))
    return _result(
        ident,
        ("5.4.9",),
        {
            "shape": data["shape"],
            "normal_depth_m": depth,
            "flow_area_m2": area,
            "wetted_perimeter_m": perimeter,
            "hydraulic_radius_m": area / perimeter,
            "surface_width_m": top,
            "velocity_m_s": q / (1000 * area),
            "capacity_lps": flow * 1000,
            "design_flow_lps": q,
            "freeboard_m": clearance,
            "required_freeboard_m": needed,
            "freeboard_satisfied": None if clearance is None else clearance >= needed,
            "adjacent_floor_clearance_satisfied": None if clearance is None else clearance >= 0.3,
        },
    )


def run_channel_capacity(inputs: Mapping[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, CHANNEL_SCHEMA)
    side, side_right = _channel_sides(d)
    q, area, perimeter, top = _manning(
        float(d["flow_depth_m"]),
        float(d["bottom_width_m"]),
        side,
        float(d["channel_gradient"]),
        float(d["manning_n"]),
        side_right,
    )
    depth = float(d["flow_depth_m"])
    return _result(
        "stormwater.as3500.channel_capacity",
        ("5.4.9",),
        {
            "shape": d["shape"],
            "flow_depth_m": depth,
            "flow_area_m2": area,
            "wetted_perimeter_m": perimeter,
            "hydraulic_radius_m": area / perimeter,
            "surface_width_m": top,
            "velocity_m_s": q / area,
            "capacity_lps": q * 1000,
            "design_flow_lps": float(d["design_flow_lps"]),
            "capacity_satisfied": q * 1000 >= float(d["design_flow_lps"]),
        },
    )


def run_channel_design(inputs: Mapping[str, Any]) -> dict[str, Any]:
    return _channel(_validated(inputs, CHANNEL_DESIGN_SCHEMA), "stormwater.as3500.channel_design")


def _friction_factor(re: float, diameter: float, roughness_m: float) -> float:
    if re <= 0:
        return 0.0
    if re <= 2300:
        return 64.0 / re
    # Transitional flow is uncertain. Interpolate between the laminar limit
    # and Colebrook at Re=4000, keeping the head-loss curve continuous.
    if re < 4000:
        fraction = (re - 2300) / 1700
        return (1 - fraction) * 64 / 2300 + fraction * _friction_factor(4000, diameter, roughness_m)
    x = 0.02
    for _ in range(100):
        y = -2.0 * log10(roughness_m / (3.7 * diameter) + 2.51 / (re * sqrt(x)))
        nxt = 1 / (y * y)
        if abs(nxt - x) < 1e-13:
            return nxt
        x = nxt
    raise ValueError("Colebrook friction iteration did not converge")


def _pipe_state(
    flow_lps: float, diameter_mm: float, roughness_mm: float, viscosity: float
) -> dict[str, float]:
    d = diameter_mm / 1000
    if roughness_mm >= diameter_mm:
        raise ValueError("Absolute roughness must be smaller than the internal bore")
    area = pi * d * d / 4
    v = flow_lps / 1000 / area
    re = v * d / viscosity
    f = _friction_factor(re, d, roughness_mm / 1000)
    return {
        "velocity_m_s": v,
        "reynolds_number": re,
        "darcy_friction_factor": f,
        "friction_slope": f * v * v / (2 * 9.80665 * d),
    }


def _pipe_capacity(
    diameter_mm: float, slope: float, roughness_mm: float, viscosity: float
) -> dict[str, float]:
    def at_velocity(v):
        return _pipe_state(
            v * pi * (diameter_mm / 1000) ** 2 / 4 * 1000,
            diameter_mm,
            roughness_mm,
            viscosity,
        )

    lo, hi = 0.0, 1.0
    for _ in range(80):
        if at_velocity(hi)["friction_slope"] >= slope:
            break
        hi *= 2
    else:
        raise ValueError("Unable to bracket pipe capacity")
    for _ in range(100):
        mid = (lo + hi) / 2
        state = at_velocity(mid)
        if state["friction_slope"] < slope:
            lo = mid
        else:
            hi = mid
    v = (lo + hi) / 2
    q = v * pi * (diameter_mm / 1000) ** 2 / 4 * 1000
    return {"capacity_lps": q, **_pipe_state(q, diameter_mm, roughness_mm, viscosity)}


def run_pipe_capacity(inputs: Mapping[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, PIPE_SCHEMA)
    state = _pipe_state(
        float(d["flow_lps"]),
        float(d["internal_diameter_mm"]),
        float(d["roughness_k_mm"]),
        float(d["kinematic_viscosity_m2_s"]),
    )
    cap = _pipe_capacity(
        float(d["internal_diameter_mm"]),
        float(d["gradient"]),
        float(d["roughness_k_mm"]),
        float(d["kinematic_viscosity_m2_s"]),
    )
    maxv = float(d.get("max_velocity_m_s", 2.0))
    rec = float(d.get("outlet_recommended_velocity_m_s", 1.5))
    return _result(
        "stormwater.as3500.pipe_capacity",
        ("5.4.11.2",),
        {
            "flow_lps": float(d["flow_lps"]),
            "internal_diameter_mm": float(d["internal_diameter_mm"]),
            "capacity_lps": cap["capacity_lps"],
            **state,
            "capacity_satisfied": float(d["flow_lps"]) <= cap["capacity_lps"],
            "maximum_velocity_m_s": maxv,
            "velocity_limit_satisfied": state["velocity_m_s"] <= maxv,
            "outlet_recommended_velocity_m_s": rec,
            "outlet_recommendation_satisfied": state["velocity_m_s"] <= rec,
        },
    )


def run_pipe_design(inputs: Mapping[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, PIPE_DESIGN_SCHEMA)
    q = float(d["flow_lps"])
    maxv = float(d.get("max_velocity_m_s", 2))
    rec = float(d.get("outlet_recommended_velocity_m_s", 1.5))
    candidates = []
    for dia in sorted(map(float, d["internal_diameters_mm"])):
        result = _pipe_capacity(
            dia,
            float(d["gradient"]),
            float(d["roughness_k_mm"]),
            float(d["kinematic_viscosity_m2_s"]),
        )
        design_state = _pipe_state(
            q, dia, float(d["roughness_k_mm"]), float(d["kinematic_viscosity_m2_s"])
        )
        if result["capacity_lps"] >= q and design_state["velocity_m_s"] <= maxv:
            candidates.append((dia, result, design_state))
            break
    if not candidates:
        raise ValueError("no supplied internal diameter meets flow and full-pipe velocity limit")
    dia, res, design_state = candidates[0]
    lo, hi = max(float(d["roughness_k_mm"]) * 1.0001, 1e-6), dia
    for _ in range(60):
        mid = (lo + hi) / 2
        capacity = _pipe_capacity(
            mid,
            float(d["gradient"]),
            float(d["roughness_k_mm"]),
            float(d["kinematic_viscosity_m2_s"]),
        )["capacity_lps"]
        if capacity < q:
            lo = mid
        else:
            hi = mid
    capacity_only_diameter = hi
    velocity_only_diameter = 1000 * sqrt(4 * q / (1000 * pi * maxv))
    return _result(
        "stormwater.as3500.pipe_design",
        ("5.4.11.2",),
        {
            "flow_lps": q,
            "selected_internal_diameter_mm": dia,
            "capacity_only_theoretical_internal_diameter_mm": capacity_only_diameter,
            "velocity_only_minimum_internal_diameter_mm": velocity_only_diameter,
            "theoretical_minimum_internal_diameter_mm": max(
                capacity_only_diameter, velocity_only_diameter
            ),
            "capacity_lps": res["capacity_lps"],
            "velocity_m_s": design_state["velocity_m_s"],
            "reynolds_number": design_state["reynolds_number"],
            "darcy_friction_factor": design_state["darcy_friction_factor"],
            "maximum_velocity_m_s": maxv,
            "velocity_limit_satisfied": True,
            "outlet_recommended_velocity_m_s": rec,
            "outlet_recommendation_satisfied": design_state["velocity_m_s"] <= rec,
            "catalogue_is_user_supplied": True,
        },
    )


def run_pipe_network(inputs: Mapping[str, Any]) -> dict[str, Any]:
    d = deepcopy(_validated(inputs, NETWORK_SCHEMA))
    nodes = {n["id"]: n for n in d["nodes"]}
    if len(nodes) != len(d["nodes"]):
        raise ValueError("node ids must be unique")
    pipes = d["pipes"]
    pids = [p["id"] for p in pipes]
    if len(set(pids)) != len(pids):
        raise ValueError("pipe ids must be unique")
    indegree = {n: 0 for n in nodes}
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for p in pipes:
        if p["from"] not in nodes or p["to"] not in nodes:
            raise ValueError(f"pipe {p['id']} references unknown node")
        outgoing[p["from"]].append(p)
        incoming[p["to"]].append(p)
        indegree[p["to"]] += 1
        a = nodes[p["from"]].get("invert_level_m")
        b = nodes[p["to"]].get("invert_level_m")
        if a is not None and b is not None and a <= b:
            raise ValueError(f"pipe {p['id']} invert grade is not falling")
        if p.get("pipe_gradient") is not None and a is not None and b is not None:
            actual = (a - b) / float(p["length_m"])
            if abs(actual - float(p["pipe_gradient"])) > max(1e-6, 0.01 * actual):
                raise ValueError(f"pipe {p['id']} declared gradient disagrees with node inverts")
    if any(len(reaches) > 1 for reaches in outgoing.values()):
        raise ValueError(
            "Bifurcations need a hydraulic flow split; only converging networks are supported"
        )
    # A single calculation represents one connected drainage system.
    adjacent = defaultdict(set)
    for p in pipes:
        adjacent[p["from"]].add(p["to"])
        adjacent[p["to"]].add(p["from"])
    connected = {next(iter(nodes))}
    todo = list(connected)
    while todo:
        for neighbour in adjacent[todo.pop()]:
            if neighbour not in connected:
                connected.add(neighbour)
                todo.append(neighbour)
    if len(connected) != len(nodes):
        raise ValueError("network contains disconnected nodes or components")
    qnode = {
        k: float(nodes[k].get("inflow_lps", 0))
        + sum(
            c["area_m2"] * c["runoff_coefficient"] * c["rainfall_intensity_mm_per_hour"] / 3600
            for c in nodes[k].get("catchments", [])
        )
        for k in nodes
    }
    local_flows = dict(qnode)
    ready = deque(k for k, v in indegree.items() if v == 0)
    seen = []
    while ready:
        n = ready.popleft()
        seen.append(n)
        for p in outgoing[n]:
            state = _pipe_state(
                qnode[n],
                float(p["internal_diameter_mm"]),
                float(p["roughness_k_mm"]),
                float(p["kinematic_viscosity_m2_s"]),
            )
            grade = p.get("pipe_gradient")
            if (
                grade is None
                and nodes[p["from"]].get("invert_level_m") is not None
                and nodes[p["to"]].get("invert_level_m") is not None
            ):
                grade = (
                    float(nodes[p["from"]]["invert_level_m"])
                    - float(nodes[p["to"]]["invert_level_m"])
                ) / float(p["length_m"])
            if grade is None or float(grade) <= 0:
                raise ValueError(
                    f"pipe {p['id']} needs falling invert levels or an explicit pipe_gradient"
                )
            p["_gradient"] = float(grade)
            cap = _pipe_capacity(
                float(p["internal_diameter_mm"]),
                float(grade),
                float(p["roughness_k_mm"]),
                float(p["kinematic_viscosity_m2_s"]),
            )
            if state["velocity_m_s"] > float(p.get("maximum_velocity_m_s", 2)):
                raise ValueError(f"pipe {p['id']} exceeds full-pipe velocity limit")
            if qnode[n] > cap["capacity_lps"]:
                raise ValueError(f"pipe {p['id']} capacity is below propagated flow")
            if p.get("cover_m") is not None and float(p["cover_m"]) < 0:
                raise ValueError(f"pipe {p['id']} has invalid cover")
            if (
                p.get("surface_level_m") is not None
                and nodes[p["from"]].get("invert_level_m") is not None
            ):
                crown = (
                    float(nodes[p["from"]]["invert_level_m"])
                    + float(p["internal_diameter_mm"]) / 1000
                )
                actual = float(p["surface_level_m"]) - crown
                if actual < 0:
                    raise ValueError(f"pipe {p['id']} crown is above the supplied surface")
                if p.get("cover_m") is not None and abs(actual - float(p["cover_m"])) > 0.01:
                    raise ValueError(f"pipe {p['id']} cover disagrees with levels")
                p["_actual_cover"] = actual
            else:
                p["_actual_cover"] = p.get("cover_m")
            if "downstream_surface_level_m" in p:
                downstream_invert = nodes[p["to"]].get("invert_level_m")
                if downstream_invert is None:
                    raise ValueError("Downstream surface needs a downstream invert level")
                downstream_cover = (
                    p["downstream_surface_level_m"]
                    - downstream_invert
                    - p["internal_diameter_mm"] / 1000
                )
                if downstream_cover < 0:
                    raise ValueError(f"pipe {p['id']} downstream crown is above the surface")
                p["_actual_cover"] = (
                    min(p["_actual_cover"], downstream_cover)
                    if p["_actual_cover"] is not None
                    else downstream_cover
                )
            if p.get("required_cover_m") is not None:
                actual_cover = p["_actual_cover"]
                if actual_cover is None:
                    raise ValueError(
                        f"pipe {p['id']} requires cover data for the supplied criterion"
                    )
                if float(actual_cover) + 1e-9 < float(p["required_cover_m"]):
                    raise ValueError(f"pipe {p['id']} is below the user-supplied required cover")
            p["_flow"] = qnode[n]
            p["_state"] = state
            qnode[p["to"]] += qnode[n]
            indegree[p["to"]] -= 1
            if indegree[p["to"]] == 0:
                ready.append(p["to"])
    if len(seen) != len(nodes):
        raise ValueError("network contains a cycle")
    if any(
        not incoming[n] and not outgoing[n] and float(nodes[n].get("inflow_lps", 0)) == 0
        for n in nodes
    ):
        raise ValueError("network contains disconnected zero-flow node")
    # Report bore changes explicitly; they may be intentional at a pit or transition.
    diameter_changes = []
    for n, ins in incoming.items():
        if ins and outgoing[n]:
            out_diameters = {float(p["internal_diameter_mm"]) for p in outgoing[n]}
            in_diameters = {float(p["internal_diameter_mm"]) for p in ins}
            if in_diameters != out_diameters:
                diameter_changes.append(
                    {
                        "node": n,
                        "incoming_diameters_mm": sorted(in_diameters),
                        "outgoing_diameters_mm": sorted(out_diameters),
                    }
                )
    rows = []
    for p in pipes:
        rows.append(
            {
                "id": p["id"],
                "from": p["from"],
                "to": p["to"],
                "flow_lps": p["_flow"],
                "internal_diameter_mm": p["internal_diameter_mm"],
                "cover_m": p.get("_actual_cover"),
                "required_cover_m": p.get("required_cover_m"),
                "capacity_lps": _pipe_capacity(
                    float(p["internal_diameter_mm"]),
                    p["_gradient"],
                    float(p["roughness_k_mm"]),
                    float(p["kinematic_viscosity_m2_s"]),
                )["capacity_lps"],
                "velocity_m_s": p["_state"]["velocity_m_s"],
                "is_outlet": p.get("outlet", False),
                "outlet_recommended_velocity_m_s": p.get("outlet_recommended_velocity_m_s", 1.5),
                "outlet_velocity_recommendation_satisfied": (
                    None
                    if not p.get("outlet", False)
                    else p["_state"]["velocity_m_s"]
                    <= float(p.get("outlet_recommended_velocity_m_s", 1.5))
                ),
                "reynolds_number": p["_state"]["reynolds_number"],
            }
        )
    return _result(
        "stormwater.as3500.pipe_network",
        ("5.4.8", "5.4.11.1", "5.4.11.2", "6.2.5"),
        {
            "node_flows_lps": qnode,
            "local_node_inflows_lps": local_flows,
            "outlet_flows_lps": {n: qnode[n] for n in nodes if not outgoing[n]},
            "flow_conservation_residual_lps": sum(local_flows.values())
            - sum(qnode[n] for n in nodes if not outgoing[n]),
            "pipes": rows,
            "topological_order": seen,
            "diameter_changes_at_junctions": diameter_changes,
            "network_capacity_checked": True,
            "surcharge_and_backwater_evaluated": False,
            "cover_basis": (
                "Minimum of supplied endpoint covers; intermediate terrain is not inferred"
            ),
            "project_cover_criteria_evaluated": any(
                p.get("required_cover_m") is not None for p in pipes
            ),
        },
    )


def _charged_state(
    q_lps: float, dmm: float, kmm: float, nu: float, length: float, coeffs: list[float]
) -> dict[str, float]:
    state = _pipe_state(q_lps, dmm, kmm, nu)
    v = state["velocity_m_s"]
    d = dmm / 1000
    vf = v * v / (2 * 9.80665)
    friction = state["darcy_friction_factor"] * length / d * vf
    minor = sum(coeffs) * vf
    return {
        **state,
        "friction_head_loss_m": friction,
        "minor_head_loss_m": minor,
        "total_head_loss_m": friction + minor,
    }


def run_charged_pipe(inputs: Mapping[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, CHARGED_SCHEMA)
    length = float(d["length_m"])
    dia = float(d["internal_diameter_mm"])
    k = float(d["roughness_k_mm"])
    nu = float(d["kinematic_viscosity_m2_s"])
    coeffs = list(map(float, d["minor_loss_coefficients"]))
    if "available_head_m" in d:
        target = float(d["available_head_m"])
        lo, hi = 0.0, 1.0
        for _ in range(80):
            if _charged_state(hi, dia, k, nu, length, coeffs)["total_head_loss_m"] >= target:
                break
            hi *= 2
        else:
            raise ValueError("Unable to bracket charged-pipe flow")
        for _ in range(120):
            mid = (lo + hi) / 2
            if _charged_state(mid, dia, k, nu, length, coeffs)["total_head_loss_m"] < target:
                lo = mid
            else:
                hi = mid
        q = (lo + hi) / 2
        if target == 0:
            q = 0.0
    else:
        q = float(d["flow_lps"])
        target = None
    result = _charged_state(q, dia, k, nu, length, coeffs)
    if target is None:
        target = (
            (float(d["upstream_level_m"]) - float(d["downstream_level_m"]))
            if "upstream_level_m" in d and "downstream_level_m" in d
            else result["total_head_loss_m"]
        )
    if "upstream_level_m" in d:
        level_head = float(d["upstream_level_m"]) - float(d["downstream_level_m"])
        if level_head < 0:
            raise ValueError("Upstream energy level must not be below downstream energy level")
        if "available_head_m" in d and abs(level_head - target) > 1e-8:
            raise ValueError("Available head disagrees with the supplied energy levels")
    return _result(
        "stormwater.as3500.charged_pipe",
        ("5.4.11.2",),
        {
            "flow_lps": q,
            "internal_diameter_mm": dia,
            "available_head_m": target,
            **result,
            "head_balance_residual_m": target - result["total_head_loss_m"],
            "head_balance_satisfied": abs(target - result["total_head_loss_m"]) < 1e-8,
            "available_head_sufficient": target + 1e-8 >= result["total_head_loss_m"],
            "flow_regime": "laminar"
            if result["reynolds_number"] <= 2300
            else ("transition" if result["reynolds_number"] < 4000 else "turbulent"),
        },
    )


CHARGED_SYSTEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["upstream_energy_level_m", "downstream_energy_level_m", "segments"],
    "properties": {
        "upstream_energy_level_m": {"type": "number"},
        "downstream_energy_level_m": {"type": "number"},
        "flow_lps": NN,
        "minimum_pressure_head_m": {"type": "number"},
        "maximum_pressure_head_m": POS,
        "segments": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id",
                    "length_m",
                    "internal_diameter_mm",
                    "roughness_k_mm",
                    "kinematic_viscosity_m2_s",
                    "minor_loss_coefficients",
                    "start_pipe_centre_level_m",
                    "end_pipe_centre_level_m",
                ],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "length_m": POS,
                    "internal_diameter_mm": POS,
                    "roughness_k_mm": NN,
                    "kinematic_viscosity_m2_s": POS,
                    "minor_loss_coefficients": {"type": "array", "items": NN},
                    "start_pipe_centre_level_m": {"type": "number"},
                    "end_pipe_centre_level_m": {"type": "number"},
                },
            },
        },
    },
}


def run_charged_pipe_system(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Steady full-pipe energy balance for a series of different internal bores."""
    d = _validated(inputs, CHARGED_SYSTEM_SCHEMA)
    head = d["upstream_energy_level_m"] - d["downstream_energy_level_m"]
    if head < 0:
        raise ValueError("Upstream energy level must be at least the downstream energy level")
    if len({s["id"] for s in d["segments"]}) != len(d["segments"]):
        raise ValueError("Charged-system segment IDs must be unique")
    for a, b in zip(d["segments"], d["segments"][1:], strict=False):
        if abs(a["end_pipe_centre_level_m"] - b["start_pipe_centre_level_m"]) > 1e-8:
            raise ValueError("Consecutive pipe segment centre levels must join")

    def states(q):
        return [
            _charged_state(
                q,
                s["internal_diameter_mm"],
                s["roughness_k_mm"],
                s["kinematic_viscosity_m2_s"],
                s["length_m"],
                s["minor_loss_coefficients"],
            )
            for s in d["segments"]
        ]

    if "flow_lps" in d:
        flow = float(d["flow_lps"])
    elif head == 0:
        flow = 0.0
    else:
        lo, hi = 0.0, 1.0
        for _ in range(80):
            if sum(s["total_head_loss_m"] for s in states(hi)) >= head:
                break
            hi *= 2
        else:
            raise ValueError("Unable to bracket charged-system flow")
        for _ in range(100):
            mid = (lo + hi) / 2
            if sum(s["total_head_loss_m"] for s in states(mid)) < head:
                lo = mid
            else:
                hi = mid
        flow = (lo + hi) / 2
    energy = float(d["upstream_energy_level_m"])
    rows = []
    for segment, state in zip(d["segments"], states(flow), strict=True):
        velocity_head = state["velocity_m_s"] ** 2 / (2 * 9.80665)
        end_energy = energy - state["total_head_loss_m"]
        rows.append(
            {
                "id": segment["id"],
                **state,
                "start_energy_level_m": energy,
                "end_energy_level_m": end_energy,
                "start_hydraulic_grade_level_m": energy - velocity_head,
                "end_hydraulic_grade_level_m": end_energy - velocity_head,
                "start_pressure_head_m": energy
                - velocity_head
                - segment["start_pipe_centre_level_m"],
                "end_pressure_head_m": end_energy
                - velocity_head
                - segment["end_pipe_centre_level_m"],
            }
        )
        energy = end_energy
    pressures = [r[k] for r in rows for k in ("start_pressure_head_m", "end_pressure_head_m")]
    minimum, maximum = min(pressures), max(pressures)
    residual = energy - d["downstream_energy_level_m"]
    return _result(
        "stormwater.as3500.charged_pipe_system",
        (),
        {
            "flow_lps": flow,
            "available_head_m": head,
            "segments": rows,
            "total_head_loss_m": d["upstream_energy_level_m"] - energy,
            "head_balance_residual_m": residual,
            "head_balance_satisfied": abs(residual) < 1e-8,
            "available_head_sufficient": residual >= -1e-8,
            "minimum_pressure_head_m": minimum,
            "maximum_pressure_head_m": maximum,
            "minimum_pressure_criterion_satisfied": minimum >= d.get("minimum_pressure_head_m", 0),
            "maximum_pressure_criterion_satisfied": (
                None
                if "maximum_pressure_head_m" not in d
                else maximum <= d["maximum_pressure_head_m"]
            ),
            "basis": (
                "Steady Darcy-Weisbach/Colebrook series energy balance; minor losses at reach ends"
            ),
            "air_entrainment_transients_and_siphonic_priming_evaluated": False,
            "pressure_checked_at_supplied_endpoints_only": True,
        },
    )


CALCULATIONS = (
    {
        "id": "stormwater.as3500.channel_capacity",
        "name": "Open-channel capacity",
        "description": "Manning capacity at supplied rectangular or trapezoidal flow depth.",
        "input_schema": CHANNEL_SCHEMA,
        "runner": run_channel_capacity,
    },
    {
        "id": "stormwater.as3500.channel_design",
        "name": "Open-channel normal depth",
        "description": (
            "Solves Manning normal depth with width, velocity, freeboard and floor clearance."
        ),
        "input_schema": CHANNEL_DESIGN_SCHEMA,
        "runner": run_channel_design,
    },
    {
        "id": "stormwater.as3500.pipe_capacity",
        "name": "Full-pipe capacity",
        "description": "Colebrook-White full circular pipe capacity and velocity checks.",
        "input_schema": PIPE_SCHEMA,
        "runner": run_pipe_capacity,
    },
    {
        "id": "stormwater.as3500.pipe_design",
        "name": "Pipe diameter selection",
        "description": (
            "Selects the smallest user-supplied internal bore meeting capacity and velocity limits."
        ),
        "input_schema": PIPE_DESIGN_SCHEMA,
        "runner": run_pipe_design,
    },
    {
        "id": "stormwater.as3500.pipe_network",
        "name": "Pipe network propagation",
        "description": "Propagates node inflows over an acyclic, invert-checked pipe network.",
        "input_schema": NETWORK_SCHEMA,
        "runner": run_pipe_network,
    },
    {
        "id": "stormwater.as3500.charged_pipe",
        "name": "Charged-pipe head balance",
        "description": "Darcy-Weisbach pipe friction and minor-loss balance or flow solve.",
        "input_schema": CHARGED_SCHEMA,
        "runner": run_charged_pipe,
    },
    {
        "id": "stormwater.as3500.charged_pipe_system",
        "name": "Charged-pipe series and hydraulic grade",
        "description": (
            "Series energy/pressure profile with supplied endpoint elevations and losses."
        ),
        "input_schema": CHARGED_SYSTEM_SCHEMA,
        "runner": run_charged_pipe_system,
    },
)
