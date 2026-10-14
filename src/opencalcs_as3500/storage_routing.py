# SPDX-License-Identifier: AGPL-3.0-only
"""Conservation-based detention outlet and level-pool routing calculations.

These methods implement supplied hydraulic equations and project curves. They are
not a council OSD prescription or a substitute for the authority's design criteria.
"""

from collections.abc import Mapping
from itertools import pairwise
from math import ceil, sqrt
from typing import Any

from opencalcs_as3500.calculations import _result, _validated

_NUMBER = {"type": "number"}
_NONNEG = {"type": "number", "minimum": 0}
_MAX_ROUTING_STEPS = 100_000

ORIFICE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["opening_area_m2", "discharge_coefficient", "head_m"],
    "properties": {
        "opening_area_m2": {"type": "number", "exclusiveMinimum": 0},
        "discharge_coefficient": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
        "head_m": _NONNEG,
        "tailwater_depth_m": _NONNEG,
        "submerged_discharge_coefficient": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
        "gravity_m_per_s2": {"type": "number", "exclusiveMinimum": 0},
    },
}
WEIR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["crest_length_m", "discharge_coefficient", "head_m"],
    "properties": {
        "crest_length_m": {"type": "number", "exclusiveMinimum": 0},
        "discharge_coefficient": {"type": "number", "exclusiveMinimum": 0},
        "head_m": _NONNEG,
        "tailwater_depth_m": _NONNEG,
        "submerged_discharge_coefficient": {"type": "number", "exclusiveMinimum": 0},
        "weir_type": {"type": "string", "enum": ["rectangular_suppressed", "broad_crested"]},
    },
}

_STAGE_STORAGE = {
    "type": "array",
    "minItems": 2,
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["stage_m", "storage_m3"],
        "properties": {"stage_m": _NUMBER, "storage_m3": _NONNEG},
    },
}
_STAGE_DISCHARGE = {
    "type": "array",
    "minItems": 2,
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["stage_m", "discharge_lps"],
        "properties": {"stage_m": _NUMBER, "discharge_lps": _NONNEG},
    },
}
_HYETOGRAPH = {
    "type": "array",
    "minItems": 1,
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["duration_s", "rainfall_intensity_mm_per_hour"],
        "properties": {
            "duration_s": {"type": "number", "exclusiveMinimum": 0},
            "rainfall_intensity_mm_per_hour": _NONNEG,
        },
    },
}
_SIZING_EVENTS = {
    "type": "array",
    "minItems": 1,
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "hyetograph"],
        "properties": {"name": {"type": "string", "minLength": 1}, "hyetograph": _HYETOGRAPH},
    },
}

ROUTING_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "hyetograph",
        "catchment_area_m2",
        "runoff_coefficient",
        "loss_rate_mm_per_hour",
        "allowable_discharge_lps",
    ],
    "properties": {
        "stage_storage": _STAGE_STORAGE,
        "stage_discharge": _STAGE_DISCHARGE,
        "tank_plan_area_m2": {"type": "number", "exclusiveMinimum": 0},
        "tank_bottom_stage_m": _NUMBER,
        "tank_top_stage_m": _NUMBER,
        "hyetograph": _HYETOGRAPH,
        "catchment_area_m2": {"type": "number", "exclusiveMinimum": 0},
        "runoff_coefficient": {"type": "number", "minimum": 0, "maximum": 1},
        "loss_rate_mm_per_hour": _NONNEG,
        "outlet": {
            "type": "object",
            "additionalProperties": False,
            "required": ["type", "coefficient"],
            "properties": {
                "type": {"type": "string", "enum": ["orifice", "weir"]},
                "coefficient": {"type": "number", "exclusiveMinimum": 0},
                "area_m2": {"type": "number", "exclusiveMinimum": 0},
                "length_m": {"type": "number", "exclusiveMinimum": 0},
                "crest_stage_m": _NUMBER,
                "tailwater_stage_m": _NUMBER,
                "submerged_coefficient": {"type": "number", "exclusiveMinimum": 0},
                "gravity_m_per_s2": {"type": "number", "exclusiveMinimum": 0},
            },
            "allOf": [
                {
                    "if": {"properties": {"type": {"const": "orifice"}}},
                    "then": {
                        "required": ["area_m2"],
                        "properties": {
                            "coefficient": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
                            "submerged_coefficient": {
                                "type": "number",
                                "exclusiveMinimum": 0,
                                "maximum": 1,
                            },
                        },
                    },
                },
                {
                    "if": {"properties": {"type": {"const": "weir"}}},
                    "then": {"required": ["length_m"]},
                },
            ],
        },
        "allowable_discharge_lps": _NONNEG,
        "flow_control_limit_lps": _NONNEG,
        "bypass_fraction": {"type": "number", "minimum": 0, "maximum": 1},
        "bypass_flow_lps": _NONNEG,
        "freeboard_m": _NONNEG,
        "initial_stage_m": _NUMBER,
        "duration_step_s": {"type": "number", "exclusiveMinimum": 0},
        "overflow_stage_m": _NUMBER,
        "overflow_coefficient": {"type": "number", "exclusiveMinimum": 0},
        "overflow_length_m": {"type": "number", "exclusiveMinimum": 0},
        "max_routing_step_s": {"type": "number", "exclusiveMinimum": 0},
    },
    "anyOf": [
        {"required": ["stage_storage"]},
        {"required": ["tank_plan_area_m2", "tank_bottom_stage_m", "tank_top_stage_m"]},
    ],
}

DETENTION_SIZING_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "hyetographs",
        "catchment_area_m2",
        "runoff_coefficient",
        "loss_rate_mm_per_hour",
        "allowable_discharge_lps",
        "tank_bottom_stage_m",
        "tank_depth_m",
        "freeboard_m",
    ],
    "properties": {
        "hyetographs": _SIZING_EVENTS,
        "catchment_area_m2": ROUTING_SCHEMA["properties"]["catchment_area_m2"],
        "runoff_coefficient": ROUTING_SCHEMA["properties"]["runoff_coefficient"],
        "loss_rate_mm_per_hour": _NONNEG,
        "allowable_discharge_lps": _NONNEG,
        "flow_control_limit_lps": _NONNEG,
        "tank_bottom_stage_m": _NUMBER,
        "tank_depth_m": {"type": "number", "exclusiveMinimum": 0},
        "freeboard_m": _NONNEG,
        "maximum_plan_area_m2": {"type": "number", "exclusiveMinimum": 0},
        "area_tolerance_m2": {"type": "number", "exclusiveMinimum": 0},
        "stage_discharge": _STAGE_DISCHARGE,
        "outlet": ROUTING_SCHEMA["properties"]["outlet"],
        "bypass_fraction": {"type": "number", "minimum": 0, "maximum": 1},
        "bypass_flow_lps": _NONNEG,
        "initial_stage_m": _NUMBER,
        "duration_step_s": {"type": "number", "exclusiveMinimum": 0},
        "max_routing_step_s": {"type": "number", "exclusiveMinimum": 0},
        "overflow_stage_m": _NUMBER,
        "overflow_coefficient": {"type": "number", "exclusiveMinimum": 0},
        "overflow_length_m": {"type": "number", "exclusiveMinimum": 0},
    },
    "anyOf": [{"required": ["stage_discharge"]}, {"required": ["outlet"]}],
}


def _curve(rows: list[dict[str, Any]], x: str, y: str, label: str) -> None:
    xs = [float(row[x]) for row in rows]
    ys = [float(row[y]) for row in rows]
    if any(b <= a for a, b in pairwise(xs)):
        raise ValueError(f"{label} {x} values must be strictly increasing")
    if any(b < a for a, b in pairwise(ys)):
        raise ValueError(f"{label} {y} values must be non-decreasing")


def _interp(x: float, xs: list[float], ys: list[float]) -> float:
    if x < xs[0] or x > xs[-1]:
        raise ValueError(f"stage {x:g} m is outside the supplied curve [{xs[0]:g}, {xs[-1]:g}] m")
    for i in range(len(xs) - 1):
        if x <= xs[i + 1]:
            f = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + f * (ys[i + 1] - ys[i])
    return ys[-1]


def run_orifice_capacity(inputs: Mapping[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, ORIFICE_SCHEMA)
    head, tail = float(d["head_m"]), float(d.get("tailwater_depth_m", 0))
    cd = float(d["discharge_coefficient"])
    submerged = tail > 0
    if submerged and "submerged_discharge_coefficient" not in d:
        raise ValueError(
            "submerged flow requires an explicitly supplied submerged_discharge_coefficient"
        )
    if submerged and tail >= head:
        raise ValueError(
            "tailwater_depth_m must be less than upstream head_m for this differential-head model"
        )
    effective_head = head - tail if submerged else head
    coeff = float(d.get("submerged_discharge_coefficient", cd)) if submerged else cd
    g = float(d.get("gravity_m_per_s2", 9.80665))
    q = (
        coeff * float(d["opening_area_m2"]) * sqrt(2 * g * effective_head)
        if effective_head
        else 0.0
    )
    return _result(
        "stormwater.as3500.detention_orifice_capacity",
        (),
        {
            "capacity_lps": q * 1000,
            "effective_head_m": effective_head,
            "discharge_coefficient": coeff,
            "flow_condition": "submerged_differential_head" if submerged else "free_discharge",
            "basis": (
                "Q = Cd A sqrt(2 g H); Cd is supplied and gravity defaults to standard gravity."
            ),
            "hydraulic_applicability": (
                "Sharp-edged opening, steady incompressible flow; approach, blockage and vortex "
                "losses are not included."
            ),
        },
    )


def run_weir_capacity(inputs: Mapping[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, WEIR_SCHEMA)
    head, tail = float(d["head_m"]), float(d.get("tailwater_depth_m", 0))
    sub = tail > 0
    if sub and "submerged_discharge_coefficient" not in d:
        raise ValueError(
            "submerged flow requires an explicitly supplied submerged_discharge_coefficient"
        )
    if sub and tail >= head:
        raise ValueError(
            "tailwater_depth_m must be less than upstream head_m for this differential-head model"
        )
    h = head - tail if sub else head
    c = (
        float(d.get("submerged_discharge_coefficient", d["discharge_coefficient"]))
        if sub
        else float(d["discharge_coefficient"])
    )
    length = float(d["crest_length_m"])
    kind = d.get("weir_type", "rectangular_suppressed")
    # Supplied coefficient convention: Q=C L H^(3/2), with C in m^(1/2)/s.
    q = c * length * h**1.5 if h else 0.0
    return _result(
        "stormwater.as3500.detention_weir_capacity",
        (),
        {
            "capacity_lps": q * 1000,
            "effective_head_m": h,
            "discharge_coefficient": c,
            "coefficient_convention": "Q = C L H^(3/2); supplied C has units m^(1/2)/s",
            "weir_type": kind,
            "flow_condition": (
                "submerged_differential_head_assumption" if sub else "free_overflow"
            ),
            "hydraulic_applicability": (
                "Valid only where the supplied coefficient matches crest shape, approach, "
                "contraction and submergence. Applying C L H^(3/2) to differential head is "
                "a caller-specified approximation, not a universal drowned-weir law."
            ),
        },
    )


def _outlet_q(stage: float, d: dict[str, Any]) -> float:
    # Optional supplied stage-discharge curve is the complete combined outlet law.
    if "stage_discharge" in d:
        rows = d["stage_discharge"]
        return _interp(
            stage, [float(r["stage_m"]) for r in rows], [float(r["discharge_lps"]) for r in rows]
        )
    o = d["outlet"]
    crest = float(o.get("crest_stage_m", 0.0))
    h = max(0.0, stage - crest)
    if o["type"] == "orifice":
        tw = float(o.get("tailwater_stage_m", -1e30))
        if tw > crest and h > 0:
            if "submerged_coefficient" not in o:
                raise ValueError("submerged outlet stage requires outlet.submerged_coefficient")
            h = max(0.0, stage - tw)
            c = float(o["submerged_coefficient"])
        else:
            c = float(o["coefficient"])
        return (
            1000 * c * float(o["area_m2"]) * sqrt(2 * float(o.get("gravity_m_per_s2", 9.80665)) * h)
            if h
            else 0.0
        )
    tw = float(o.get("tailwater_stage_m", -1e30))
    if tw > crest and h > 0:
        if "submerged_coefficient" not in o:
            raise ValueError("submerged weir stage requires outlet.submerged_coefficient")
        h = max(0.0, stage - tw)
        coefficient = float(o["submerged_coefficient"])
    else:
        coefficient = float(o["coefficient"])
    return 1000 * coefficient * float(o["length_m"]) * h**1.5 if h else 0.0


def _route(data: dict[str, Any]) -> dict[str, Any]:
    if "stage_storage" not in data:
        bottom = float(data["tank_bottom_stage_m"])
        top = float(data["tank_top_stage_m"])
        if top <= bottom:
            raise ValueError("tank_top_stage_m must be above tank_bottom_stage_m")
        plan_area = float(data["tank_plan_area_m2"])
        data["stage_storage"] = [
            {"stage_m": bottom, "storage_m3": 0.0},
            {"stage_m": top, "storage_m3": plan_area * (top - bottom)},
        ]
    if "stage_discharge" not in data and "outlet" not in data:
        raise ValueError("supply either stage_discharge or an outlet configuration")
    ss = data["stage_storage"]
    _curve(ss, "stage_m", "storage_m3", "stage-storage curve")
    stages = [float(r["stage_m"]) for r in ss]
    stores = [float(r["storage_m3"]) for r in ss]
    if stores[0] != 0:
        raise ValueError("stage_storage curve must start at zero storage")
    if any(b <= a for a, b in pairwise(stores)):
        raise ValueError("stage_storage curve storage_m3 values must be strictly increasing")
    if "stage_discharge" in data:
        _curve(data["stage_discharge"], "stage_m", "discharge_lps", "stage-discharge curve")
    if "duration_step_s" in data:
        step = float(data["duration_step_s"])
        if step <= 0:
            raise ValueError("duration_step_s must be positive")
    else:
        step = min(float(x["duration_s"]) for x in data["hyetograph"])
    max_step = float(data.get("max_routing_step_s", step))
    step = min(step, max_step)
    if step <= 0:
        raise ValueError("routing step must be positive")
    required_steps = sum(ceil(float(block["duration_s"]) / step) for block in data["hyetograph"])
    if required_steps > _MAX_ROUTING_STEPS:
        raise ValueError(
            f"routing requires {required_steps} steps, exceeding "
            f"the {_MAX_ROUTING_STEPS}-step limit"
        )
    area = float(data["catchment_area_m2"])
    runoff = float(data["runoff_coefficient"])
    loss = float(data["loss_rate_mm_per_hour"])
    # Respect actual duration even when a block duration is not an integer multiple of step.
    time = []
    qin = []
    t = 0.0
    for block in data["hyetograph"]:
        remaining = float(block["duration_s"])
        q = (
            area
            * runoff
            * max(0.0, float(block["rainfall_intensity_mm_per_hour"]) - loss)
            / 3600
            / 1000
        )
        while remaining > 1e-9:
            dt = min(step, remaining)
            t += dt
            time.append(t)
            qin.append(q)
            remaining -= dt
    frac = float(data.get("bypass_fraction", 0))
    fixed = float(data.get("bypass_flow_lps", 0)) / 1000
    storage = 0.0
    stage = stages[0]
    if "initial_stage_m" in data:
        stage = float(data["initial_stage_m"])
        storage = _interp(stage, stages, stores)
    if storage > stores[-1]:
        raise ValueError("initial storage exceeds supplied stage-storage curve")
    hydro = []
    peak_s = storage
    peak_stage = stage
    peak_time = 0.0
    overflow_vol = 0.0
    balance_in = 0.0
    balance_out = 0.0
    volume_limited_steps = 0
    total_volume_limited_correction = 0.0
    peak_site_discharge = 0.0
    rainfall_in_volume = 0.0
    bypass_volume = 0.0
    overflow_stage = float(data.get("overflow_stage_m", stages[-1]))
    if (
        "overflow_stage_m" in data
        and not {"overflow_coefficient", "overflow_length_m"} <= data.keys()
    ):
        raise ValueError("overflow_stage_m requires overflow_coefficient and overflow_length_m")
    if "overflow_stage_m" in data and overflow_stage >= stages[-1]:
        raise ValueError(
            "stage-storage curve must extend above overflow_stage_m to route overflow hydraulically"
        )
    for end, qraw in zip(time, qin, strict=True):
        dt = end - (hydro[-1]["time_s"] if hydro else 0.0)
        qbypass = min(qraw, frac * qraw + fixed)
        qcontrolled = max(0.0, qraw - qbypass)
        flow_limit = float(data.get("flow_control_limit_lps", float("inf"))) / 1000

        # Allowable discharge is a design criterion. Only an explicitly supplied
        # physical flow-control device can limit the routed outlet.
        def outlet_at(s: float, max_flow: float = flow_limit) -> tuple[float, float]:
            main = min(_outlet_q(s, data) / 1000, max_flow)
            over = 0.0
            if "overflow_stage_m" in data and s > overflow_stage:
                over = (
                    float(data["overflow_coefficient"])
                    * float(data["overflow_length_m"])
                    * (s - overflow_stage) ** 1.5
                )
            return main, over

        # Modified Puls: 2S/dt + Qout = 2Sprev/dt - Qprev + Iprev + Icur.
        prev_main, prev_over = outlet_at(stage) if storage > 1e-12 else (0.0, 0.0)
        # Each hyetograph block is a constant intensity over its own interval.
        # Do not interpolate across the previous block boundary.
        inflow_avg = qcontrolled
        rhs = 2 * storage / dt - prev_main - prev_over + inflow_avg * 2
        lo, hi = stages[0], stages[-1]
        for _ in range(80):
            mid = (lo + hi) / 2
            sm = _interp(mid, stages, stores)
            qm, qo = outlet_at(mid)
            if 2 * sm / dt + qm + qo < rhs:
                lo = mid
            else:
                hi = mid
        new_stage = (lo + hi) / 2
        new_storage = _interp(new_stage, stages, stores)
        # Reject curve exceedance without an explicit overflow rule.
        if rhs > 2 * stores[-1] / dt + sum(outlet_at(stages[-1])):
            raise ValueError("routing exceeds supplied stage-storage curve range")
        qmain, qoverflow = outlet_at(new_stage)
        if new_storage <= 1e-12:
            # The storage curve bottom is the dry state, where no outlet flow remains.
            qmain = qoverflow = 0.0
        avg_main = (prev_main + qmain) / 2
        avg_over = (prev_over + qoverflow) / 2
        raw_out_volume = (avg_main + avg_over) * dt
        available_water = storage + inflow_avg * dt
        correction = max(0.0, raw_out_volume - available_water)
        volume_limited = correction > max(1e-12, available_water * 1e-10)
        if volume_limited:
            scale = available_water / raw_out_volume if raw_out_volume else 0.0
            avg_main *= scale
            avg_over *= scale
            new_storage = 0.0
            new_stage = stages[0]
            qmain = qoverflow = 0.0
            volume_limited_steps += 1
            total_volume_limited_correction += correction
        actual_out_volume = available_water if volume_limited else raw_out_volume
        overflow_vol += avg_over * dt
        balance_in += inflow_avg * dt
        rainfall_in_volume += qraw * dt
        bypass_volume += qbypass * dt
        balance_out += actual_out_volume
        peak_site_discharge = max(
            peak_site_discharge,
            (prev_main + prev_over + qbypass) * 1000,
            (qmain + qoverflow + qbypass) * 1000,
        )
        hydro.append(
            {
                "time_s": end,
                "duration_s": dt,
                "rainfall_inflow_lps": qraw * 1000,
                "bypass_lps": qbypass * 1000,
                "controlled_inflow_lps": qcontrolled * 1000,
                "outlet_lps": qmain * 1000,
                "overflow_lps": qoverflow * 1000,
                "interval_average_outlet_lps": avg_main * 1000,
                "interval_average_overflow_lps": avg_over * 1000,
                "volume_limited_discharge_correction_lps": correction * 1000 / dt,
                "volume_limited_at_dry_boundary": volume_limited,
                "site_discharge_peak_estimate_lps": max(prev_main + prev_over, qmain + qoverflow)
                * 1000
                + qbypass * 1000,
                "stage_m": new_stage,
                "storage_m3": new_storage,
            }
        )
        storage, stage = new_storage, new_stage
        if storage > peak_s:
            peak_s = storage
            peak_stage = stage
            peak_time = end
    residual = (
        balance_in
        - (storage - (_interp(float(data.get("initial_stage_m", stages[0])), stages, stores)))
        - balance_out
    )
    fb = float(data.get("freeboard_m", 0))
    capacity_stage = stages[-1] - fb
    # Adequacy is reported only when positive freeboard was supplied.
    available_storage = (
        _interp(capacity_stage, stages, stores)
        if stages[0] <= capacity_stage <= stages[-1]
        else None
    )
    if "stage_discharge" in data:
        outlet_assumption = "caller-supplied stage-discharge curve is the complete outlet law"
    elif data["outlet"]["type"] == "weir":
        outlet = data["outlet"]
        crest = float(outlet.get("crest_stage_m", 0.0))
        tailwater = float(outlet.get("tailwater_stage_m", -1e30))
        if tailwater > crest:
            outlet_assumption = (
                "caller-supplied submerged_coefficient applies C L H^(3/2) to differential "
                "head; this is not a universal drowned-weir law"
            )
        else:
            outlet_assumption = "free-weir Q = C L H^(3/2) with caller-supplied coefficient"
    else:
        outlet_assumption = (
            "orifice law uses supplied discharge coefficient and differential head if submerged"
        )
    return {
        "hydrograph": hydro,
        "peak_storage_m3": peak_s,
        "peak_stage_m": peak_stage,
        "peak_storage_time_s": peak_time,
        "total_controlled_inflow_m3": balance_in,
        "total_rainfall_inflow_m3": rainfall_in_volume,
        "total_bypass_volume_m3": bypass_volume,
        "total_discharge_and_overflow_m3": balance_out,
        "mass_balance_error_m3": residual,
        "total_overflow_m3": overflow_vol,
        "freeboard_m": fb,
        "available_storage_below_freeboard_m3": available_storage,
        "storage_within_freeboard": peak_stage <= capacity_stage if fb > 0 else None,
        "allowable_discharge_lps": float(data["allowable_discharge_lps"]),
        "peak_total_site_discharge_lps": peak_site_discharge,
        "allowable_discharge_satisfied": peak_site_discharge
        <= float(data["allowable_discharge_lps"]) + 1e-9,
        "flow_control_limit_lps": data.get("flow_control_limit_lps"),
        "outlet_hydraulic_assumption": outlet_assumption,
        "volume_limited_step_count": volume_limited_steps,
        "total_volume_limited_discharge_correction_m3": total_volume_limited_correction,
        "routing_step_s": step,
        "bypass_fraction": frac,
        "basis": (
            "Modified Puls level-pool continuity with piecewise-linear supplied curves "
            "and trapezoidal flux integration."
        ),
    }


def run_detention_routing(inputs: Mapping[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, ROUTING_SCHEMA)
    results = _route(d)
    return _result("stormwater.as3500.detention_routing", (), results)


def run_detention_storage_sizing(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Find a rectangular tank plan area that passes every supplied event."""
    d = _validated(inputs, DETENTION_SIZING_SCHEMA)
    event_names = [event["name"] for event in d["hyetographs"]]
    if len(set(event_names)) != len(event_names):
        raise ValueError("hyetographs event names must be unique")
    depth = float(d["tank_depth_m"])
    freeboard = float(d["freeboard_m"])
    if freeboard >= depth:
        raise ValueError("freeboard_m must be less than tank_depth_m")
    bottom = float(d["tank_bottom_stage_m"])
    top = bottom + depth
    usable_top = top - freeboard
    maximum_area = float(d.get("maximum_plan_area_m2", 100000.0))
    tolerance = float(d.get("area_tolerance_m2", 1e-4))
    if "initial_stage_m" in d and float(d["initial_stage_m"]) > usable_top:
        raise ValueError("initial_stage_m must not exceed the top of usable storage")

    def evaluate(plan_area: float) -> tuple[bool, list[dict[str, Any]]]:
        event_results = []
        for event in d["hyetographs"]:
            route_data = {
                key: value
                for key, value in d.items()
                if key
                not in {
                    "hyetographs",
                    "tank_bottom_stage_m",
                    "tank_depth_m",
                    "freeboard_m",
                    "maximum_plan_area_m2",
                    "area_tolerance_m2",
                }
            }
            route_data.update(
                {
                    "hyetograph": event["hyetograph"],
                    "tank_plan_area_m2": plan_area,
                    "tank_bottom_stage_m": bottom,
                    "tank_top_stage_m": top,
                }
            )
            try:
                result = _route(route_data)
            except ValueError as exc:
                if "routing exceeds supplied stage-storage curve range" in str(exc):
                    return False, event_results + [
                        {
                            "event": event["name"],
                            "storage_satisfied": False,
                            "failure": "tank storage range exceeded",
                        }
                    ]
                raise
            storage_satisfied = result["peak_stage_m"] <= usable_top + 1e-10
            discharge_satisfied = result["allowable_discharge_satisfied"]
            satisfied = storage_satisfied and discharge_satisfied
            event_results.append(
                {
                    "event": event["name"],
                    "peak_storage_m3": result["peak_storage_m3"],
                    "peak_stage_m": result["peak_stage_m"],
                    "storage_satisfied": storage_satisfied,
                    "peak_total_site_discharge_lps": result["peak_total_site_discharge_lps"],
                    "allowable_discharge_satisfied": discharge_satisfied,
                    "sizing_criteria_satisfied": satisfied,
                    "mass_balance_error_m3": result["mass_balance_error_m3"],
                    "total_controlled_inflow_m3": result["total_controlled_inflow_m3"],
                    "total_discharge_and_overflow_m3": result["total_discharge_and_overflow_m3"],
                    "routing_step_s": result["routing_step_s"],
                }
            )
            if not satisfied:
                return False, event_results
        return True, event_results

    lo, hi = 0.0, min(1.0, maximum_area)
    satisfied, _ = evaluate(hi)
    while not satisfied and hi < maximum_area:
        lo = hi
        hi = min(maximum_area, hi * 2)
        satisfied, _ = evaluate(hi)
    if not satisfied:
        events = evaluate(hi)[1]
        return _result(
            "stormwater.as3500.detention_storage_sizing",
            (),
            {
                "minimum_plan_area_m2": None,
                "maximum_plan_area_m2": hi,
                "sizing_satisfied": False,
                "event_results_at_maximum_area": events,
                "basis": (
                    "bounded bisection on rectangular plan area across all supplied hyetographs"
                ),
            },
        )
    while hi - lo > tolerance:
        mid = (lo + hi) / 2
        ok, _ = evaluate(mid)
        if ok:
            hi = mid
        else:
            lo = mid
    _, event_results = evaluate(hi)
    return _result(
        "stormwater.as3500.detention_storage_sizing",
        (),
        {
            "minimum_plan_area_m2": hi,
            "maximum_plan_area_m2": maximum_area,
            "tank_depth_m": depth,
            "freeboard_m": freeboard,
            "usable_storage_depth_m": depth - freeboard,
            "usable_storage_volume_m3": hi * (depth - freeboard),
            "area_tolerance_m2": tolerance,
            "sizing_satisfied": True,
            "event_results": event_results,
            "basis": (
                "bounded bisection on rectangular plan area across all supplied hyetographs "
                "using the supplied outlet and discharge limit"
            ),
            "limitations": [
                "results apply only to supplied rainfall events, outlet law, allowable "
                "discharge and level-pool model",
                "does not select authority-specific OSD criteria or assert regulatory compliance",
            ],
        },
    )


CALCULATIONS = (
    {
        "id": "stormwater.as3500.detention_orifice_capacity",
        "name": "Detention orifice capacity",
        "description": "Orifice discharge using supplied coefficient and submergence inputs.",
        "input_schema": ORIFICE_SCHEMA,
        "runner": run_orifice_capacity,
    },
    {
        "id": "stormwater.as3500.detention_weir_capacity",
        "name": "Detention weir capacity",
        "description": "Weir discharge using a supplied coefficient and stated convention.",
        "input_schema": WEIR_SCHEMA,
        "runner": run_weir_capacity,
    },
    {
        "id": "stormwater.as3500.detention_routing",
        "name": "Detention level-pool routing",
        "description": (
            "Modified Puls routing from supplied rainfall/losses and storage/outlet data; "
            "project-specific OSD conditions required."
        ),
        "input_schema": ROUTING_SCHEMA,
        "runner": run_detention_routing,
    },
    {
        "id": "stormwater.as3500.detention_storage_sizing",
        "name": "Detention storage sizing",
        "description": (
            "Find a rectangular storage plan area for supplied rainfall events and outlet criteria."
        ),
        "input_schema": DETENTION_SIZING_SCHEMA,
        "runner": run_detention_storage_sizing,
    },
)
