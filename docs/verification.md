# Calculation verification

## Method

The source basis was reviewed against AS/NZS 3500.3:2025. Independent arithmetic cases use the implemented clause equations and compare their expected values against package outputs to an absolute tolerance of 1e-9. The independent cases and comparison results are generated in validation/benchmarks.json.

The standard's published Appendix K pumped-system example is treated as a separate comparison, not as an independent benchmark. It provides a useful external numeric check of the event volume, 30-minute pumping volume, and remaining storage calculation.

## Independent cases

| Case | Inputs | Independently checked result |
|---|---|---|
| Single-slope roof catchment | 100 m2 roof plan area; 30 degree slope | Area factor 1.2886751346; catchment area 128.867513459 m2 |
| Steel roof flow | 1,000 m2; coefficient 0.9; 180 mm/h | 45 L/s |
| Pervious runoff coefficient | 44.4 mm/h 10-year, 60-minute intensity; multiplier 1.0; no soil adjustment | 0.35752 |
| Mixed surface design flow | 400 m2 at 0.9, 600 m2 at 0.85, 500 m2 at 0.35752; 180 mm/h | 52.438 L/s |
| Rectangular Manning channel | 0.30 m bottom width; 0.15 m flow depth; 0.01 gradient; n = 0.013 | 61.561614885 L/s |
| Sag-pit inlet | 4 m free inlet perimeter; 0.10 m ponding; blockage factor 0.5 | 101.192885 L/s |

The example cases are illustrative calculations with explicit assumptions. The rainfall values and coefficients are inputs, not general design values for other locations or storms.

## Published worked-example comparison

Appendix K uses a 1,000 m2 catchment, runoff coefficient 0.9, 44.4 mm/h 10% AEP rainfall intensity for 120 minutes, and 30 L/s pumping. Direct arithmetic gives 79.92 m3 runoff and 54 m3 pumped in 30 minutes, leaving 25.92 m3 storage. These round to the example's 80 m3 event volume and 26 m3 storage. The package also checks the separate minimum wet-well storage of 1% of catchment area and at least 3 m3.

The source values and comparison basis are summarized in validation/published_examples.json. No standard extracts are reproduced.

## Limits of evidence

The automated checks establish agreement between this implementation and the documented equation arithmetic for the selected cases. They do not establish that a rainfall input, AEP multiplier, roughness value, blockage factor, pump selection, catchment boundary, soil description, or project detail is appropriate. The plugin does not claim full AS/NZS 3500.3 compliance.
