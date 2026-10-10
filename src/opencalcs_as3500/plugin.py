"""OpenCalcs plugin entry point and calculation descriptors."""

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from opencalcs_as3500 import __version__
from opencalcs_as3500.calculations import (
    run_design_flow,
    run_open_channel_capacity,
    run_pervious_coefficient,
    run_pumped_storage,
    run_roof_catchment,
    run_roof_flow,
    run_sag_pit_capacity,
)
from opencalcs_as3500.schemas import (
    DESIGN_FLOW_INPUT_SCHEMA,
    OPEN_CHANNEL_INPUT_SCHEMA,
    OUTPUT_SCHEMA,
    PERVIOUS_COEFFICIENT_INPUT_SCHEMA,
    PUMPED_STORAGE_INPUT_SCHEMA,
    ROOF_CATCHMENT_INPUT_SCHEMA,
    ROOF_CATCHMENT_OUTPUT_SCHEMA,
    ROOF_FLOW_INPUT_SCHEMA,
    SAG_PIT_INPUT_SCHEMA,
)
from opencalcs_as3500.standards import STANDARD, StandardReference


@dataclass(frozen=True)
class Calculation:
    id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    runner: Callable[[Mapping[str, Any]], dict[str, Any]]
    version: str = "1"
    standard: StandardReference = STANDARD
    output_schema: dict[str, Any] = field(default_factory=lambda: deepcopy(OUTPUT_SCHEMA))

    def run(self, inputs: Mapping[str, Any]) -> dict[str, Any]:
        return self.runner(inputs)

    def descriptor(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "discipline": "stormwater",
            "category": "drainage-design",
            "jurisdiction": "AU",
            "version": self.version,
            "standard": self.standard.descriptor(),
            "input_schema": deepcopy(self.input_schema),
            "output_schema": deepcopy(self.output_schema),
        }


def _calculations() -> tuple[Calculation, ...]:
    return (
        Calculation(
            "stormwater.as3500.roof_catchment",
            "Roof catchment area",
            "Freely exposed flat roofs or single-slope eaves-gutter roof catchment area.",
            deepcopy(ROOF_CATCHMENT_INPUT_SCHEMA),
            run_roof_catchment,
            output_schema=deepcopy(ROOF_CATCHMENT_OUTPUT_SCHEMA),
        ),
        Calculation(
            "stormwater.as3500.roof_flow",
            "Roof design flow",
            (
                "Roof flow using supplied design rainfall intensity and the Australian Clause "
                "5.4.6 roofed-area coefficient."
            ),
            deepcopy(ROOF_FLOW_INPUT_SCHEMA),
            run_roof_flow,
        ),
        Calculation(
            "stormwater.as3500.pervious_runoff_coefficient",
            "Pervious-area runoff coefficient",
            "Australian unroofed-pervious runoff coefficient from Clause 5.4.6.",
            deepcopy(PERVIOUS_COEFFICIENT_INPUT_SCHEMA),
            run_pervious_coefficient,
        ),
        Calculation(
            "stormwater.as3500.design_flow",
            "Surface design flow",
            "Combined surface runoff flow from plan-area subcatchments and supplied coefficients.",
            deepcopy(DESIGN_FLOW_INPUT_SCHEMA),
            run_design_flow,
        ),
        Calculation(
            "stormwater.as3500.open_channel_capacity",
            "Open-channel capacity",
            (
                "Rectangular or trapezoidal open-channel capacity by the Clause 5.4.9 "
                "Manning equation."
            ),
            deepcopy(OPEN_CHANNEL_INPUT_SCHEMA),
            run_open_channel_capacity,
        ),
        Calculation(
            "stormwater.as3500.sag_pit_capacity",
            "Sag-pit inlet capacity",
            "Sag-pit inlet capacity for ponding depth up to 120 mm.",
            deepcopy(SAG_PIT_INPUT_SCHEMA),
            run_sag_pit_capacity,
        ),
        Calculation(
            "stormwater.as3500.pumped_storage",
            "Pumped-system storage",
            "Clause 8.3.6 effective storage with the 10% AEP, 120-minute event.",
            deepcopy(PUMPED_STORAGE_INPUT_SCHEMA),
            run_pumped_storage,
        ),
    )


@dataclass(frozen=True)
class AS3500Plugin:
    id: str = "stormwater.as3500"
    name: str = "OpenCalcs Stormwater Drainage"
    version: str = __version__
    revision: str | None = None
    license: str = "AGPL-3.0-only"
    source: str = "https://github.com/Elandu/OpenCalcs-AS3500"
    calculations: tuple[Calculation, ...] = field(default_factory=_calculations)

    def descriptor(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "revision": self.revision,
            "license": self.license,
            "source": self.source,
            "calculations": [calculation.descriptor() for calculation in self.calculations],
        }


def get_plugin() -> AS3500Plugin:
    """Return plugin metadata without starting a service."""

    return AS3500Plugin()
