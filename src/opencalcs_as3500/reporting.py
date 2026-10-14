# SPDX-License-Identifier: AGPL-3.0-only
"""Reproducible calculation packs and optional printable PDF reports."""

from __future__ import annotations

import json
from hashlib import sha256
from html import escape
from pathlib import Path
from typing import Any

from opencalcs_as3500.calculations import _result, _validated

TEXT = {"type": "string", "maxLength": 5000}
REPORT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "runs"],
    "properties": {
        "title": {**TEXT, "minLength": 1},
        "job_number": TEXT,
        "prepared_by": TEXT,
        "company": TEXT,
        "project_address": TEXT,
        "notes": TEXT,
        "runs": {
            "type": "array",
            "minItems": 1,
            "maxItems": 100,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["calculation", "inputs"],
                "properties": {
                    "calculation": {"type": "string", "minLength": 1},
                    "inputs": {"type": "object"},
                },
            },
        },
    },
}


def run_calculation_pack(inputs: dict[str, Any]) -> dict[str, Any]:
    from opencalcs_as3500 import __version__
    from opencalcs_as3500.plugin import get_plugin

    d = _validated(inputs, REPORT_SCHEMA)
    calculations = {c.id: c for c in get_plugin().calculations}
    rows = []
    for item in d["runs"]:
        ident = item["calculation"]
        if ident == "stormwater.as3500.calculation_pack":
            raise ValueError("Calculation packs may not recursively contain calculation packs")
        if ident not in calculations:
            raise ValueError(f"Unknown calculation in report: {ident}")
        result = calculations[ident].run(item["inputs"])
        canonical = json.dumps(
            {"inputs": item["inputs"], "output": result},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        rows.append(
            {
                "calculation": ident,
                "name": calculations[ident].name,
                "inputs": item["inputs"],
                "output": result,
                "sha256": sha256(canonical.encode()).hexdigest(),
            }
        )
    # Every report is generated from freshly executed inputs, never unchecked supplied outputs.
    header = "".join(
        f"<p><b>{escape(k.replace('_', ' ').title())}:</b> {escape(d[k])}</p>"
        for k in ("company", "job_number", "project_address", "prepared_by")
        if k in d
    )
    sections = []
    for row in rows:
        sections.append(
            f"<section><h2>{escape(row['name'])}</h2>"
            f"<p>{escape(row['calculation'])}</p>"
            f"<h3>Inputs</h3><pre>{escape(json.dumps(row['inputs'], indent=2))}</pre>"
            f"<h3>Results and basis</h3><pre>{escape(json.dumps(row['output'], indent=2))}</pre>"
            f"<p>Record SHA-256: {row['sha256']}</p></section>"
        )
    html = (
        "<!doctype html><html><head><meta charset='utf-8'><title>"
        + escape(d["title"])
        + "</title><style>"
        "body{font:14px Arial,sans-serif;margin:30px;max-width:1000px;color:#172b3a}"
        "h1,h2{color:#173f56}pre{white-space:pre-wrap;overflow-wrap:anywhere;"
        "background:#f1f5f8;padding:12px}section{break-before:page}"
        "@media print{body{margin:15mm}pre{font-size:9pt}}"
        "</style></head><body><h1>"
        + escape(d["title"])
        + "</h1>"
        + header
        + f"<p>OpenCalcs-AS3500 {__version__}. Australian design inputs.</p>"
        + "<p>Selected calculation methods only. This report does not establish whole-standard "
        "or project compliance. Source ratings, design storms, detailing and stated method "
        "limits require project review.</p>"
        + ("<p>" + escape(d["notes"]).replace("\n", "<br>") + "</p>" if d.get("notes") else "")
        + "".join(sections)
        + "</body></html>"
    )
    return _result(
        "stormwater.as3500.calculation_pack",
        (),
        {
            "title": d["title"],
            "package_version": __version__,
            "run_count": len(rows),
            "job_details": {k: v for k, v in d.items() if k != "runs"},
            "runs": rows,
            "html": html,
        },
    )


def write_pdf(inputs: dict[str, Any], path: str | Path) -> Path:
    """Write a paginated report; install the ``reports`` extra to use this helper."""
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    result = run_calculation_pack(inputs)["results"]
    styles = getSampleStyleSheet()
    styles["Normal"].fontSize = 9
    styles["Normal"].leading = 12
    styles["Code"].fontSize = 7
    styles["Code"].leading = 9
    styles["Code"].wordWrap = "CJK"
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(output),
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=result["title"],
        author=inputs.get("prepared_by", ""),
    )
    story = [Paragraph(escape(result["title"]), styles["Title"])]
    for key, value in result["job_details"].items():
        if key != "title":
            story.append(
                Paragraph(
                    f"<b>{escape(key.replace('_', ' ').title())}</b>: "
                    f"{escape(value).replace(chr(10), '<br/>')}",
                    styles["Normal"],
                )
            )
    story += [
        Spacer(1, 5 * mm),
        Paragraph(
            f"OpenCalcs-AS3500 {result['package_version']}. Selected methods only. "
            "Full-standard and project compliance have not been evaluated. "
            "Review source data, method limitations and project criteria.",
            styles["Normal"],
        ),
    ]

    def text(value: Any) -> str:
        if value is None:
            return "Not evaluated"
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, float):
            # Exact values remain in the JSON record and hash. Keep the printout legible.
            return str(float(f"{value:.10g}"))
        if isinstance(value, list) and all(not isinstance(v, (dict, list)) for v in value):
            return ", ".join(text(v) for v in value) or "None"
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=True, indent=2)
        return str(value)

    def label(key: str) -> str:
        units = {
            "mm_per_hour": "mm/h",
            "m2_s": "m2/s",
            "m_s": "m/s",
            "lps": "L/s",
            "mm2": "mm2",
            "mm": "mm",
            "m3": "m3",
            "m2": "m2",
            "m": "m",
            "s": "s",
        }
        for suffix, unit in units.items():
            if key.endswith("_" + suffix):
                return key[: -(len(suffix) + 1)].replace("_", " ").capitalize() + f" [{unit}]"
        return key.replace("_", " ").capitalize()

    for row in result["runs"]:
        story.extend(
            [
                PageBreak(),
                Paragraph(escape(row["name"]), styles["Heading1"]),
                Paragraph(escape(row["calculation"]), styles["Normal"]),
            ]
        )
        metadata = {k: v for k, v in row["output"].items() if k != "results"}
        for section_title, values in (
            ("Inputs", row["inputs"]),
            ("Results", row["output"]["results"]),
            ("Method record", metadata),
        ):
            story.append(Paragraph(section_title, styles["Heading2"]))
            data = [
                [
                    Paragraph(escape(label(str(k))), styles["Normal"]),
                    Paragraph(escape(text(v)).replace("\n", "<br/>"), styles["Normal"]),
                ]
                for k, v in values.items()
            ]
            # Individual nested values are split into paragraph lines so large hydrographs
            # are not forced into an unsplittable table row.
            for v in values.values():
                if len(text(v)) > 1200:
                    data = None
                    break
            if data is None:
                for k, v in values.items():
                    story.append(Paragraph(escape(label(str(k))), styles["Heading3"]))
                    for line in text(v).splitlines():
                        story.append(Paragraph(escape(line) or "&#160;", styles["Code"]))
            else:
                table = Table(data, colWidths=[75 * mm, 95 * mm], hAlign="LEFT", splitInRow=1)
                table.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf3f7")),
                        ]
                    )
                )
                story.append(table)
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Record SHA-256: " + row["sha256"], styles["Normal"]))

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.drawString(18 * mm, 10 * mm, f"OpenCalcs-AS3500 | {doc.page}")

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output


CALCULATIONS = (
    {
        "id": "stormwater.as3500.calculation_pack",
        "name": "Drainage calculation report",
        "description": (
            "Execute a calculation pack with job details, source records and printable HTML."
        ),
        "input_schema": REPORT_SCHEMA,
        "runner": run_calculation_pack,
    },
)
