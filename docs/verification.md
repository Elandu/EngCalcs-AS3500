# Calculation verification

## Version 0.3 verification

The extension has 38 registered calculations. Every calculation has a schema-checked executable example and is exercised through the installed host registry and HTTP API. The release evidence is recorded in `validation/release_checks.json`; the commands below reproduce the source checks. CI repeats them on Python 3.12 and 3.13 and installs the wheel outside the checkout.

Local release acceptance on Python 3.12.10 passed **225 source tests and 225 installed-wheel tests, with zero failures, errors or skips**. Both numerical-report generators passed in both environments. Ruff, formatting, compilation, metadata parsing, dependency consistency, wheel/sdist builds and distribution-content audits passed. The three-page sample PDF was also visually reviewed. Remote CI results are recorded separately on the pull request.

```powershell
python -m ruff check .
python -m ruff format --check .
python -m compileall -q src tests
python tests/verification_report.py
python tests/suite_verification_report.py
python -m pytest -q
python -m build
```

`validation/benchmarks.json` retains ten independent arithmetic cases. `validation/suite_benchmarks.json` adds thirteen cases with 25 numerical comparisons: explicit fixed-gradient Colebrook substitution; Hagen-Poiseuille series-pipe flow; asymmetric Manning normal depth; constant-volume storage; an analytical linear reservoir under timestep refinement; orifice/weir discharge; valley geometry; roof sheet capacity; historical CSIRO Imperial-unit conversions; grouped roof/wall geometry; and published Appendix I box/rainhead readings. Each comparison records its own units, expected value, tolerance and actual error. The reservoir comparison allows the declared Modified Puls discretization error; chart readings are separate from equation precision.

Domain tests cover missing/nonfinite inputs, chart bounds and context, inclusive table boundaries, correlated wind cases, network conservation and invalid topology, downstream cover, theoretical/catalogue bores, zero-head flow, series pressures, CSV validation, piecewise-constant rainfall volumes, dry storage, bypass/overflow discharge, passive outlets versus explicit flow controls, storage sizing, CLI errors, report hashes and PDF pagination.

The pristine integration host is `Elandu/EngCalcs` revision `3f3dcb260a311521cc56d23d8c94f970ab763c86`, installed from Git into an isolated Python 3.12 environment. Wheel acceptance runs outside the source checkout and verifies that imports resolve to `site-packages`. It does not depend on changes in the user's separate host checkout. Distributions are audited for licensed source material, recovered third-party code and generated previews.

### Source and chart review

The reviewed current standard, two historical editions and the user's scanned Martin (1973) paper are identified by reference and SHA-256 in `validation/source_review.json`. Source documents remain private. Current-standard procedures, historical research and general hydraulic models have distinct provenance.

Appendix H supports published example anchors and conservative bounded graph envelopes. H.1 envelopes retain the larger unadjusted depth, without taking a gradient reduction. H.3 length uses the adopted rainhead depth and the gutter-depth curve. Other chart envelopes select the adverse sampled flow/width and disclose visual-reading allowances. These are deliberately conservative selections, not exact digitization or equations fitted to RGD results. The independent graph-boundary tests prevent the underreads found during review.

Automatic valley selection above 20 m2 remains disabled because the supplied 2025 Figure 3.6.2 has an unresolved physical-monotonicity inconsistency. The 2018 and 2021 editions and the provided standards folder were checked; no applicable correction was located. The small-catchment table and separate hydraulic diagnostics are supported. RGD's unavailable CFD solver is not reproduced.

## Legacy arithmetic method

The source basis was reviewed against AS/NZS 3500.3:2025. Independent arithmetic cases use the clause equations and compare their expected values against package outputs to an absolute tolerance of 1e-9. The independent cases and comparison results are generated in validation/benchmarks.json. The examples for both flat and single-slope roofs, both open-channel shapes, and each pervious-soil adjustment are included.

The standard's published Appendix K pumped-system example is treated as a separate comparison, not as an independent benchmark. It provides a useful external numeric check of the event volume, 30-minute pumping volume, and remaining storage calculation.

## Historical version 0.2 release checks

For package version 0.2.0, all 26 plugin and OpenCalcs host tests passed with the built wheel installed. The registry test runs all seven example inputs, and the HTTP test runs the roof-flow calculation. All ten independent benchmarks passed with a maximum absolute difference of 0.0. Ruff checks, formatting, compilation, wheel build, and source-distribution build also passed.

## Independent cases

| Case | Inputs | Independently checked result |
|---|---|---|
| Flat roof catchment | 240 m2 plan area including any gutters | 240 m2 |
| Single-slope roof catchment | 100 m2 roof plan area; 30 degree slope | Area factor 1.2886751346; catchment area 128.867513459 m2 |
| Australian roof flow | 1,000 m2; Clause 5.4.6 coefficient 1.0; 180 mm/h | 50 L/s |
| Pervious runoff coefficient | 44.4 mm/h 10-year, 60-minute intensity; multiplier 1.0; no soil adjustment | 0.35752 |
| Pervious coefficient with clay adjustment | 44.4 mm/h; multiplier 0.85; clay soil | 0.403892 |
| Pervious coefficient with sandy-soil adjustment | 44.4 mm/h; multiplier 1.05; sandy soil | 0.275396 |
| Roof, impervious, and pervious design flow | 400 m2 at 1.0, 600 m2 at 0.9, 500 m2 at 0.35752; 180 mm/h | 55.938 L/s |
| Rectangular Manning channel | 0.30 m bottom width; 0.15 m flow depth; 0.01 gradient; n = 0.013 | 61.561614885 L/s |
| Trapezoidal Manning channel | 0.40 m bottom width; 0.20 m flow depth; 1:1 side slope; 0.01 gradient; n = 0.013 | 229.862578079 L/s |
| Sag-pit inlet | 4 m free inlet perimeter; 0.10 m ponding; blockage factor 0.5 | 101.192885 L/s |

The example cases are illustrative calculations with explicit assumptions. The rainfall values and coefficients are inputs, not general design values for other locations or storms.

## Published worked-example comparison

Appendix K uses a 1,000 m2 catchment, runoff coefficient 0.9, 44.4 mm/h 10% AEP rainfall intensity for 120 minutes, and 30 L/s pumping. Direct arithmetic gives 79.92 m3 runoff and 54 m3 pumped in 30 minutes, leaving 25.92 m3 storage. These round to the example's 80 m3 event volume and 26 m3 storage. The package also checks the separate minimum wet-well storage of 1% of catchment area and at least 3 m3.

Clause 5.4.6(a)(i) specifies 1.0 for Australian roofed areas, while Appendix K's pumped example supplies 0.9. The roof-flow calculation follows Clause 5.4.6; the pumped-storage calculation uses Appendix K's coefficient only as a supplied example input and does not determine whether it is appropriate for another catchment.

The source values and comparison basis are summarized in validation/published_examples.json. No standard extracts are reproduced.

The unit suite also checks the Clause 8.3.6 minimum-storage branch: for the same 1,000 m2 example catchment with a 40 L/s pump, the residual runoff volume is below the 10 m3 wet-well minimum, so the required wet-well volume is 10 m3.

## Limits of evidence

The automated checks establish agreement between this implementation and the documented equation arithmetic for the selected cases. They do not establish that a rainfall input, AEP multiplier, roughness value, blockage factor, pump selection, catchment boundary, soil description, or project detail is appropriate. The plugin does not claim full AS/NZS 3500.3 compliance.
