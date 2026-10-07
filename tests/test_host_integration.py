"""Optional integration checks against an installed OpenCalcs host."""

import asyncio
import json
from importlib.metadata import entry_points
from pathlib import Path

import pytest

PLUGIN_ENTRY = next(
    (item for item in entry_points(group="opencalcs.plugins") if item.name == "as3500"),
    None,
)
if PLUGIN_ENTRY is None:
    pytest.skip(
        "Install this wheel and the OpenCalcs host to run integration checks.",
        allow_module_level=True,
    )

ROOT = Path(__file__).resolve().parents[1]


def _inputs(filename: str) -> dict:
    return json.loads((ROOT / "examples" / filename).read_text(encoding="utf-8"))


def test_entry_point_registers_calculations_and_registry_runs_examples():
    pytest.importorskip("opencalcs")
    from opencalcs.registry import CalculationRegistry

    plugin = PLUGIN_ENTRY.load()()
    registry = CalculationRegistry()
    assert plugin.id == "stormwater.as3500"
    assert len(plugin.calculations) == 7
    examples = {
        "stormwater.as3500.roof_catchment": "roof_catchment.json",
        "stormwater.as3500.roof_flow": "roof_flow.json",
        "stormwater.as3500.pervious_runoff_coefficient": "pervious_runoff_coefficient.json",
        "stormwater.as3500.design_flow": "surface_design_flow.json",
        "stormwater.as3500.open_channel_capacity": "open_channel_capacity.json",
        "stormwater.as3500.sag_pit_capacity": "sag_pit_capacity.json",
        "stormwater.as3500.pumped_storage": "pumped_storage.json",
    }
    results = {
        calculation_id: registry.run(calculation_id, _inputs(filename))
        for calculation_id, filename in examples.items()
    }
    assert set(results) == {calculation.id for calculation in plugin.calculations}
    assert results["stormwater.as3500.roof_flow"]["results"]["runoff_coefficient"] == 1.0
    assert results["stormwater.as3500.roof_flow"]["results"]["design_flow_lps"] == pytest.approx(50)
    result = results["stormwater.as3500.pumped_storage"]
    assert result["results"]["storm_runoff_volume_m3"] == pytest.approx(79.92)
    assert result["_provenance"]["engine"]["id"] == "stormwater.as3500"
    assert result["_provenance"]["standard"]["edition"] == "2025"


def test_host_http_catalog_and_calculation_run():
    pytest.importorskip("opencalcs")
    httpx = pytest.importorskip("httpx")
    from opencalcs.api import create_app
    from opencalcs.auth import AllowAllAuthenticator

    async def request_routes():
        transport = httpx.ASGITransport(app=create_app(authenticator=AllowAllAuthenticator()))
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            descriptor = await client.get("/api/v1/calculations/stormwater.as3500.sag_pit_capacity")
            result = await client.post(
                "/api/v1/calculations/stormwater.as3500.sag_pit_capacity/run",
                json={"inputs": _inputs("sag_pit_capacity.json")},
            )
            roof_descriptor = await client.get("/api/v1/calculations/stormwater.as3500.roof_flow")
            roof_result = await client.post(
                "/api/v1/calculations/stormwater.as3500.roof_flow/run",
                json={"inputs": _inputs("roof_flow.json")},
            )
        return descriptor, result, roof_descriptor, roof_result

    descriptor, result, roof_descriptor, roof_result = asyncio.run(request_routes())
    assert descriptor.status_code == 200
    assert result.status_code == 200
    assert result.json()["results"]["capacity_lps"] == pytest.approx(1600 * 0.5 * 4 * 0.1**1.5)
    assert roof_descriptor.status_code == 200
    assert roof_result.status_code == 200
    assert roof_result.json()["results"]["runoff_coefficient"] == 1.0
    assert roof_result.json()["results"]["design_flow_lps"] == pytest.approx(50)
