"""Public command-line entry point acceptance checks."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "opencalcs_as3500", *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_catalog_and_calculation_execution(tmp_path):
    catalog = cli("list")
    assert catalog.returncode == 0, catalog.stderr
    descriptor = json.loads(catalog.stdout)
    ids = {c["id"] for c in descriptor["calculations"]}
    assert "stormwater.as3500.charged_pipe_system" in ids
    output = tmp_path / "roof.json"
    response = cli(
        "run",
        "stormwater.as3500.roof_flow",
        "--input",
        ROOT / "examples" / "roof_flow.json",
        "--output",
        output,
    )
    assert response.returncode == 0, response.stderr
    assert json.loads(output.read_text())["results"]["design_flow_lps"] == 50
    invalid = cli("run", "unknown", "--input", ROOT / "examples" / "roof_flow.json")
    assert invalid.returncode == 2
    assert "Unknown calculation" in invalid.stderr


def test_cli_report_exports_html(tmp_path):
    output = tmp_path / "report.html"
    response = cli(
        "report",
        "--input",
        ROOT / "examples" / "calculation_pack.json",
        "--format",
        "html",
        "--output",
        output,
    )
    assert response.returncode == 0, response.stderr
    html = output.read_text(encoding="utf-8")
    assert "Record SHA-256" in html
    assert "Roof design flow" in html


@pytest.mark.parametrize(
    "record",
    [[], {"calculation": "stormwater.as3500.pipe_design", "inputs": {}}],
)
def test_cli_rejects_nonobject_or_mismatched_wrapper(tmp_path, record):
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    response = cli("run", "stormwater.as3500.roof_flow", "--input", path)
    assert response.returncode == 2
    assert "Calculation failed:" in response.stderr


def test_cli_report_rejects_mismatched_wrapper(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"calculation": "other", "inputs": {}}), encoding="utf-8")
    response = cli("report", "--input", path, "--output", tmp_path / "report.html")
    assert response.returncode == 2
    assert "does not match" in response.stderr
