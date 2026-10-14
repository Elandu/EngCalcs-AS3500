"""Source-record selection, strict CSV and reproducible report checks."""

import json
from pathlib import Path

import pytest

from opencalcs_as3500.reporting import run_calculation_pack
from opencalcs_as3500.workflows import run_csv_import, run_rainfall_selection


def test_rainfall_depth_is_converted_with_exact_event_selection():
    d = {
        "location": "Doncaster example",
        "purpose": "box_gutter",
        "source": "Appendix I example",
        "records": [
            {
                "location": "Doncaster example",
                "aep_percent": 1,
                "duration_minutes": 5,
                "depth_mm": 14.9,
            }
        ],
    }
    r = run_rainfall_selection(d)["results"]
    assert r["design_rainfall_intensity_mm_per_hour"] == pytest.approx(178.8)
    assert r["rainfall_retrieved_from_bom"] is False
    d["purpose"] = "eaves"
    with pytest.raises(ValueError, match="No exact"):
        run_rainfall_selection(d)


def test_csv_strict_schema_and_numbers():
    header = "catchment_id,area_m2,runoff_coefficient\n"
    r = run_csv_import({"kind": "catchments", "csv_text": header + "roof,100,1\n"})["results"]
    assert r["rows"] == [{"catchment_id": "roof", "area_m2": 100.0, "runoff_coefficient": 1.0}]
    for text in [
        header + "roof,100,1,extra\n",
        header + "roof,nan,1\n",
        header + "roof,10,1\nroof,20,1\n",
        header + "roof,10,\n",
    ]:
        with pytest.raises(ValueError):
            run_csv_import({"kind": "catchments", "csv_text": text})


def test_report_executes_fresh_results_is_deterministic_and_escapes_html():
    d = {
        "title": "<script>alert(1)</script>",
        "runs": [
            {
                "calculation": "stormwater.as3500.roof_flow",
                "inputs": {"catchment_area_m2": 1000, "design_rainfall_intensity_mm_per_hour": 180},
            }
        ],
    }
    a = run_calculation_pack(d)["results"]
    b = run_calculation_pack(d)["results"]
    assert a == b
    assert a["runs"][0]["output"]["results"]["design_flow_lps"] == 50
    assert "<script>" not in a["html"]
    assert "&lt;script&gt;" in a["html"]
    assert len(a["runs"][0]["sha256"]) == 64
    with pytest.raises(ValueError, match="recursively"):
        run_calculation_pack(
            {
                "title": "bad",
                "runs": [{"calculation": "stormwater.as3500.calculation_pack", "inputs": {}}],
            }
        )


def test_pdf_export_contains_results_job_metadata_and_page_numbers(tmp_path):
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    from opencalcs_as3500.reporting import write_pdf

    inputs = {
        "title": "Drainage review",
        "job_number": "VALIDATION-3500",
        "runs": [
            {
                "calculation": "stormwater.as3500.roof_flow",
                "inputs": {"catchment_area_m2": 1000, "design_rainfall_intensity_mm_per_hour": 180},
            }
        ],
    }
    output = write_pdf(inputs, tmp_path / "pack.pdf")
    reader = pypdf.PdfReader(output)
    assert len(reader.pages) >= 2
    text = "\n".join(page.extract_text() for page in reader.pages)
    for expected in (
        "VALIDATION-3500",
        "Roof design flow",
        "50.0",
        "AS/NZS 3500.3:2025",
        "Record SHA-256",
        "OpenCalcs-AS3500 | 2",
    ):
        assert expected in text


def test_pdf_example_keeps_compact_arrays_and_record_hashes_with_their_calculations(tmp_path):
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    from opencalcs_as3500.reporting import write_pdf

    path = Path(__file__).resolve().parents[1] / "examples" / "calculation_pack.json"
    inputs = json.loads(path.read_text(encoding="utf-8"))["inputs"]
    reader = pypdf.PdfReader(write_pdf(inputs, tmp_path / "pack.pdf"))
    assert len(reader.pages) == 3
    records = run_calculation_pack(inputs)["results"]["runs"]
    for page, record in zip(reader.pages[1:], records, strict=True):
        text = page.extract_text()
        assert record["name"] in text
        assert record["sha256"] in text
    assert "100, 150, 225, 300, 375, 450" in reader.pages[2].extract_text()
