"""Every published descriptor has an executable, schema-valid, reproducible example."""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from opencalcs_as3500.plugin import get_plugin

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = json.loads((ROOT / "examples" / "manifest.json").read_text(encoding="utf-8"))
CALCULATIONS = {c.id: c for c in get_plugin().calculations}


def test_example_manifest_covers_exact_registered_catalog():
    assert set(EXAMPLES) == set(CALCULATIONS)


@pytest.mark.parametrize("ident", sorted(CALCULATIONS))
def test_calculation_example_schema_finite_and_input_immutable(ident):
    calculation = CALCULATIONS[ident]
    descriptor = calculation.descriptor()
    Draft202012Validator.check_schema(descriptor["input_schema"])
    Draft202012Validator.check_schema(descriptor["output_schema"])
    record = json.loads((ROOT / "examples" / EXAMPLES[ident]).read_text(encoding="utf-8"))
    inputs = record.get("inputs", record)
    before = copy.deepcopy(inputs)
    Draft202012Validator(descriptor["input_schema"]).validate(inputs)
    result = calculation.run(inputs)
    assert inputs == before
    Draft202012Validator(descriptor["output_schema"]).validate(result)
    assert result["calculation"] == ident
    assert result["full_standard_compliance"] is False
    assert result["standard_compliance_evaluated"] is False
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("ident", sorted(CALCULATIONS))
def test_missing_inputs_fail_as_validation_error(ident):
    with pytest.raises(ValueError):
        CALCULATIONS[ident].run({})


def test_method_provenance_distinguishes_research_and_general_hydraulics():
    for ident, calculation in CALCULATIONS.items():
        descriptor = calculation.descriptor()
        if ".csiro_" in ident:
            assert descriptor["method_family"] == "historical_research"
            assert descriptor["standard"]["edition"] == "1973"
        elif ".detention_" in ident or ident.endswith("charged_pipe_system"):
            assert descriptor["method_family"] == "general_engineering"
            assert descriptor["standard"] is None
