# EngCalcs stormwater drainage plugin

An independently versioned OpenCalcs plugin for Australian stormwater calculations. Version 0.3 adds roof drainage workflows, pipes, networks, charged systems, channels, detention routing and sizing, rainfall records, CSV and calculation reports.

## Calculation families

| Area | Tools |
|---|---|
| Catchments | Flat/sloping/partially exposed roofs, adjacent roofs, walls, correlated wind cases, higher-roof discharge and spreader details |
| Eaves | Figure 3.5.5 gutter sizing, Table 3.5.2 downpipes, exact manufacturer ratings, count/catchment checks, Appendix F overflow, historical CSIRO long-gutter sizing |
| Box gutters | Appendix H box, rainhead, sump, side and high-capacity overflow procedures; independent normal/critical-depth diagnostics; historical CSIRO box/receiver estimates |
| Pipes | Colebrook-White capacity, theoretical bore and catalogue selection, velocity, converging networks, individual node rainfall, invert/cover checks, CSV execution |
| Charged systems | Darcy-Weisbach friction and minor losses, head/flow solve, series pipes and hydraulic-grade/pressure profiles |
| Channels and valleys | Manning capacity/normal depth, asymmetric and triangular sections, widths/velocities, floor clearance/freeboard; valley table selection and separate hydraulic/wave-allowance checks |
| Storage | Pumped storage, orifice/weir capacity, level-pool routing, bypass/overflow and rectangular detention storage sizing across supplied storms |
| Workflow | Exact location/AEP/duration rainfall-record selection, strict CSV import, fresh calculation packs with job details, hashes, HTML and PDF |

[Coverage and limits](docs/coverage.md), [RGD comparison](docs/rgd_gap_audit.md), and [verification](docs/verification.md) explain the method boundaries. Every registered tool has an executable example in [the manifest](examples/manifest.json).

## Install and run

Requires Python 3.12 or later. Install the built wheel in the same environment as the OpenCalcs host:

```powershell
python -m pip install .
# PDF export:
python -m pip install ".[reports]"
python -m opencalcs_as3500 list
python -m opencalcs_as3500 run stormwater.as3500.roof_flow --input examples/roof_flow.json
python -m opencalcs_as3500 report --input examples/calculation_pack.json --output report.pdf --format pdf
```

The command-line alias is `opencalcs-as3500`. The stable plugin entry point remains `as3500 = opencalcs_as3500.plugin:get_plugin`. The host discovers installed calculations without source changes. All inputs and outputs are JSON with explicit unit suffixes; gradients are dimensionless rise/run, not a 1:N denominator.

```python
from opencalcs_as3500.plugin import get_plugin

calculations = {c.id: c for c in get_plugin().calculations}
result = calculations["stormwater.as3500.roof_flow"].run(
    {
        "catchment_area_m2": 1000,
        "design_rainfall_intensity_mm_per_hour": 180,
    }
)
assert result["results"]["design_flow_lps"] == 50
```

## Source and design inputs

Current-standard methods reference **AS/NZS 3500.3:2025**. The CSIRO methods reference K. G. Martin's **1973** research separately. General hydraulic tools carry no claim to be a current-standard design procedure. The Australian roofed-area coefficient is **1.0**.

Supply project rainfall, coefficients, catchment geometry, product internal bores, hydraulic losses, outlet data and authority criteria. The plugin selects events from supplied rainfall records; it does not download BOM IFD data or infer time of concentration. Manufacturer catalogue ratings retain their source. Appendix H support and the unresolved large-valley graph are described explicitly in the coverage documentation.

Results always set `full_standard_compliance=false` and `standard_compliance_evaluated=false`. Numerical checks do not assess every installation detail, authority rule, project condition or CFD performance requirement. Licensed standards and recovered third-party implementation code are not included.

## Development

```powershell
python -m pip install -e ".[dev,reports]"
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m build
python tests/verification_report.py
```

Host integration tests require OpenCalcs. CI installs a pinned public host revision and repeats the tests against the installed wheel outside this checkout. A skipped integration module is not evidence of host acceptance.

## Licensing

This revision is proprietary; see [LICENSE](LICENSE) and [LICENSING.md](LICENSING.md). Historical AGPL revisions retain the rights previously granted. Legacy `opencalcs` identifiers remain for compatibility.
