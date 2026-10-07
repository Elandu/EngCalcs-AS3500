# Calculation coverage

## Standard basis

The implemented basis is AS/NZS 3500.3:2025, Plumbing and drainage - Part 3: Stormwater drainage. The package targets Australian design inputs and runoff-coefficient choices; it does not implement the New Zealand-specific runoff tables. The source edition is recorded in every calculation descriptor and result. No standard pages, scans, OCR, or extracted text are included in this repository.

## Implemented methods

| Calculation | Clause basis | Included scope |
|---|---|---|
| Roof catchment area | 3.4.3.1 and 3.4.3.2 | Freely exposed flat roofs and single-slope roofs draining to eaves gutters; the flat-roof plan area includes contributing gutters, and the single-slope factor is evaluated from roof angle. |
| Roof design flow | 5.4.6 and 5.4.8 | Supplied design intensity and one of the listed Australian roof-surface coefficients. |
| Pervious runoff coefficient | 5.4.6 | Australian equation, intensity limits, one of the Table 5.4.6(A) multipliers, and sandy/clay soil adjustment. |
| Surface design flow | 5.4.7 and 5.4.8 | Plan-area subcatchments with supplied coefficients and design rainfall intensity. |
| Open-channel capacity | 5.4.9 | Rectangular or trapezoidal wetted section and user-selected Manning roughness. |
| Sag-pit capacity | 5.4.10.1 | Inlet perimeter, blockage factor, and ponding depth no greater than 0.12 m. |
| Pumped-system storage | 8.3.6 | The 10% AEP, 120-minute runoff volume, pump volume over 30 minutes, and minimum wet-well storage. Pump capacity is an input that must be separately selected and checked under Clause 8.4(a). |

## Input meaning

- Areas are in square metres.
- Rainfall intensity is in millimetres per hour.
- Flow is in litres per second.
- For a flat roof, the plan area includes any gutters. For a single-slope roof, enter the roof plan area used by Clause 3.4.3.2.
- Roof slope is in degrees and is limited to 0 through 65 degrees. The supported roof-area equations require freely exposed roofs.
- Channel depth, perimeter, and hydraulic radius are in metres.
- Manning roughness and channel gradient are dimensionless.
- Pumped-system volumes are in cubic metres.
- The pervious-area runoff-coefficient multiplier m must correspond to the selected AEP in Table 5.4.6(A). The accepted values are 0.8, 0.85, 0.95, 1.0, 1.05, 1.15, 1.2, and 1.25.
- For the pumped-storage calculation, the rainfall intensity must be the 10% AEP, 120-minute intensity for the project location.

The intensity and AEP values must be selected by the designer from the applicable rainfall source and standard method. The package does not calculate IFD values, time of concentration, or rainfall temporal patterns.

## Exclusions

This package does not implement all of AS/NZS 3500.3. In particular, it does not size partially exposed roof catchments, box gutters, downpipes, vertical-wall catchments, roof spreaders, pipe networks, culverts, on-grade pits, pumps, wet wells, surcharge paths, or complete site drainage. It does not select a suitable storm or site-specific coefficients for unsupported surfaces, assess floor clearances or freeboard, perform hydraulic modelling, or check other standards, NCC provisions, local authority requirements, or construction details.

The implemented methods are calculation aids for the listed clauses. A passing numeric capacity or storage result is not a statement that a project complies with the standard.
