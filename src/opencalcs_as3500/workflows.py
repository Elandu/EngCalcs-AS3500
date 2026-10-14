# SPDX-License-Identifier: LicenseRef-EngCalcs-Proprietary
"""Rainfall record selection and strict bulk catchment/pipe CSV import."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from opencalcs_as3500.calculations import _result, _validated

POS = {"type": "number", "exclusiveMinimum": 0}
TEXT = {"type": "string", "minLength": 1}
RAINFALL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["location", "purpose", "source", "records"],
    "properties": {
        "location": TEXT,
        "source": TEXT,
        "source_date": TEXT,
        "purpose": {
            "enum": ["eaves", "roof_overflow", "box_gutter", "site_surface", "pumped_storage"]
        },
        "aep_percent": {"type": "number", "exclusiveMinimum": 0, "maximum": 100},
        "duration_minutes": POS,
        "records": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["location", "aep_percent", "duration_minutes"],
                "properties": {
                    "location": TEXT,
                    "aep_percent": {**POS, "maximum": 100},
                    "duration_minutes": POS,
                    "intensity_mm_per_hour": POS,
                    "depth_mm": POS,
                },
                "oneOf": [{"required": ["intensity_mm_per_hour"]}, {"required": ["depth_mm"]}],
            },
        },
    },
    "allOf": [
        {
            "if": {"properties": {"purpose": {"const": "site_surface"}}},
            "then": {"required": ["aep_percent", "duration_minutes"]},
        }
    ],
}
CSV_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["kind", "csv_text"],
    "properties": {"kind": {"enum": ["catchments", "pipes", "rainfall"]}, "csv_text": TEXT},
}


def run_rainfall_selection(inputs: dict[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, RAINFALL_SCHEMA)
    defaults = {
        "eaves": (5, 5),
        "roof_overflow": (1, 5),
        "box_gutter": (1, 5),
        "pumped_storage": (10, 120),
    }
    if d["purpose"] == "site_surface":
        if "aep_percent" not in d:
            raise ValueError("site_surface requires the project's selected aep_percent")
        aep, duration = d["aep_percent"], d["duration_minutes"]
    else:
        aep, duration = defaults[d["purpose"]]
        if d.get("aep_percent", aep) != aep or d.get("duration_minutes", duration) != duration:
            raise ValueError("Rainfall AEP/duration does not match the selected Australian purpose")
    seen = set()
    for row in d["records"]:
        key = (row["location"], row["aep_percent"], row["duration_minutes"])
        if key in seen:
            raise ValueError("Duplicate rainfall location/AEP/duration record")
        seen.add(key)
    matches = [
        r
        for r in d["records"]
        if r["location"] == d["location"]
        and r["aep_percent"] == aep
        and r["duration_minutes"] == duration
    ]
    if len(matches) != 1:
        raise ValueError(
            "No exact location/AEP/duration rainfall record; interpolation is not implied"
        )
    row = matches[0]
    intensity = row.get("intensity_mm_per_hour", row.get("depth_mm", 0) * 60 / duration)
    return _result(
        "stormwater.as3500.rainfall_selection",
        ("3.3.4", "3.3.5", "5.4.5", "8.3.6"),
        {
            "location": d["location"],
            "purpose": d["purpose"],
            "jurisdiction": "AU",
            "aep_percent": aep,
            "duration_minutes": duration,
            "design_rainfall_intensity_mm_per_hour": intensity,
            "rainfall_depth_mm": intensity * duration / 60,
            "source": d["source"],
            "source_date": d.get("source_date"),
            "source_records_supplied_by_user": True,
            "rainfall_retrieved_from_bom": False,
        },
    )


def run_csv_import(inputs: dict[str, Any]) -> dict[str, Any]:
    d = _validated(inputs, CSV_SCHEMA)
    if len(d["csv_text"]) > 2_000_000:
        raise ValueError("CSV input exceeds 2 MB limit")
    reader = csv.DictReader(StringIO(d["csv_text"].lstrip("\ufeff")), strict=True)
    expected = {
        "catchments": {"catchment_id": str, "area_m2": float, "runoff_coefficient": float},
        "pipes": {
            "pipe_id": str,
            "upstream_node": str,
            "downstream_node": str,
            "length_m": float,
            "internal_diameter_mm": float,
            "upstream_invert_m": float,
            "downstream_invert_m": float,
        },
        "rainfall": {
            "location": str,
            "aep_percent": float,
            "duration_minutes": float,
            "depth_mm": float,
        },
    }[d["kind"]]
    try:
        headings = reader.fieldnames
        records = list(reader)
    except csv.Error as exc:
        raise ValueError(f"Malformed CSV: {exc}") from exc
    if headings is None or len(headings) != len(set(headings)):
        raise ValueError("CSV must have unique column headings")
    if set(headings) != set(expected):
        raise ValueError(f"CSV columns must be exactly: {', '.join(expected)}")
    rows = []
    for n, row in enumerate(records, 2):
        if n > 10001:
            raise ValueError("CSV may contain at most 10000 records")
        if None in row or any(value is None or not value.strip() for value in row.values()):
            raise ValueError(f"CSV row {n} has missing or excess fields")
        try:
            parsed = {k: converter(row[k].strip()) for k, converter in expected.items()}
        except (TypeError, ValueError) as exc:
            raise ValueError(f"CSV row {n} contains an invalid number") from exc
        # The shared result validator rejects NaN and infinity recursively.
        if d["kind"] == "catchments":
            if parsed["area_m2"] <= 0 or not 0 <= parsed["runoff_coefficient"] <= 1:
                raise ValueError(f"CSV row {n} has invalid catchment area or coefficient")
        elif d["kind"] == "pipes":
            if parsed["length_m"] <= 0 or parsed["internal_diameter_mm"] <= 0:
                raise ValueError(f"CSV row {n} has invalid length or internal bore")
        elif (
            min(parsed[k] for k in ("aep_percent", "duration_minutes", "depth_mm")) <= 0
            or parsed["aep_percent"] > 100
        ):
            raise ValueError(f"CSV row {n} has invalid rainfall data")
        rows.append(parsed)
    if not rows:
        raise ValueError("CSV contains no data records")
    id_field = {"catchments": "catchment_id", "pipes": "pipe_id"}.get(d["kind"])
    if id_field and len({r[id_field] for r in rows}) != len(rows):
        raise ValueError(f"CSV contains duplicate {id_field} values")
    return _result(
        "stormwater.as3500.csv_import",
        (),
        {
            "kind": d["kind"],
            "row_count": len(rows),
            "rows": rows,
            "units": "Column suffixes are explicit SI units; pipe diameters are internal bores.",
        },
    )


NETWORK_CSV_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["pipe_csv", "node_inflows_lps", "roughness_k_mm", "kinematic_viscosity_m2_s"],
    "properties": {
        "pipe_csv": TEXT,
        "node_inflows_lps": {
            "type": "object",
            "additionalProperties": {"type": "number", "minimum": 0},
        },
        "roughness_k_mm": {"type": "number", "minimum": 0},
        "kinematic_viscosity_m2_s": POS,
        "required_cover_m": {"type": "number", "minimum": 0},
        "node_surface_levels_m": {"type": "object", "additionalProperties": {"type": "number"}},
    },
    "allOf": [
        {"if": {"required": ["required_cover_m"]}, "then": {"required": ["node_surface_levels_m"]}}
    ],
}


def run_pipe_network_csv(inputs: dict[str, Any]) -> dict[str, Any]:
    """Import pipe geometry, reconcile junction inverts, and execute the network solver."""
    from opencalcs_as3500.hydraulics import run_pipe_network

    d = _validated(inputs, NETWORK_CSV_SCHEMA)
    rows = run_csv_import({"kind": "pipes", "csv_text": d["pipe_csv"]})["results"]["rows"]
    nodes = {}
    pipes = []
    for row in rows:
        for column, invert in (
            ("upstream_node", "upstream_invert_m"),
            ("downstream_node", "downstream_invert_m"),
        ):
            name, level = row[column], row[invert]
            if name in nodes and abs(nodes[name]["invert_level_m"] - level) > 1e-8:
                raise ValueError(f"Conflicting invert levels for junction {name}")
            nodes[name] = {
                "id": name,
                "invert_level_m": level,
                "inflow_lps": d["node_inflows_lps"].get(name, 0),
            }
        pipe = {
            "id": row["pipe_id"],
            "from": row["upstream_node"],
            "to": row["downstream_node"],
            "length_m": row["length_m"],
            "internal_diameter_mm": row["internal_diameter_mm"],
            "roughness_k_mm": d["roughness_k_mm"],
            "kinematic_viscosity_m2_s": d["kinematic_viscosity_m2_s"],
        }
        surface = d.get("node_surface_levels_m", {})
        if "required_cover_m" in d and any(
            row[key] not in surface for key in ("upstream_node", "downstream_node")
        ):
            raise ValueError("Every pipe endpoint requires a surface level for cover checks")
        if row["upstream_node"] in surface:
            pipe["surface_level_m"] = surface[row["upstream_node"]]
        if row["downstream_node"] in surface:
            pipe["downstream_surface_level_m"] = surface[row["downstream_node"]]
        if "required_cover_m" in d:
            pipe["required_cover_m"] = d["required_cover_m"]
        pipes.append(pipe)
    if set(d["node_inflows_lps"]) - nodes.keys():
        raise ValueError("An inflow references a node absent from the pipe CSV")
    if set(d.get("node_surface_levels_m", {})) - nodes.keys():
        raise ValueError("A surface level references a node absent from the pipe CSV")
    network = {"nodes": list(nodes.values()), "pipes": pipes}
    checked = run_pipe_network(network)
    return _result(
        "stormwater.as3500.pipe_network_csv",
        tuple(checked["clauses"]),
        {
            "network_inputs": network,
            "network_results": checked["results"],
            "csv_pipe_count": len(rows),
        },
    )


CALCULATIONS = (
    {
        "id": "stormwater.as3500.rainfall_selection",
        "name": "Rainfall selection",
        "description": "Select an exact location, AEP and duration from supplied source records.",
        "input_schema": RAINFALL_SCHEMA,
        "runner": run_rainfall_selection,
    },
    {
        "id": "stormwater.as3500.csv_import",
        "name": "Bulk drainage CSV import",
        "description": "Parse unit-explicit catchment, pipe and rainfall CSV data.",
        "input_schema": CSV_SCHEMA,
        "runner": run_csv_import,
    },
    {
        "id": "stormwater.as3500.pipe_network_csv",
        "name": "Pipe network from CSV",
        "description": "Import pipe geometry, reconcile junctions and run hydraulic checks.",
        "input_schema": NETWORK_CSV_SCHEMA,
        "runner": run_pipe_network_csv,
    },
)
