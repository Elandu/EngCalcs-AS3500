# Calculation coverage

## Basis and boundaries

The package targets Australian inputs. Selected standard procedures reference AS/NZS 3500.3:2025. Historical CSIRO methods reference Martin (1973); general hydraulic methods use their stated equations and supplied project data. Descriptors distinguish these method families, and host provenance does not identify general methods as current-standard calculations.

All results retain `full_standard_compliance=false` and `standard_compliance_evaluated=false`. These tools do not assess an entire project or all provisions of the standard. No licensed pages, scans, OCR, extracted source text, or recovered third-party implementation code are distributed.

## Implemented scope

| Calculation suffixes (prefix `stormwater.as3500.`) | Basis | Scope |
|---|---|---|
| `roof_catchment`, `roof_flow` | 3.4.3, 5.4.6, 5.4.8 | Legacy freely exposed geometry, Australian roof coefficient 1.0, supplied intensity |
| `roof_catchment_plan` | 3.4.3-3.4.4 | Grouped flat, exposed/partially exposed, adjacent-roof and wall geometry; shared wind scenarios and governing totals |
| `higher_catchment_diagnostic` | 3.4.5 | Upper/lower catchment accounting, treated strips/material details, supplied downstream capacities |
| `eaves_gutter_chart`, `eaves_gutter_system`, `eaves_overflow` | 3.5, Appendix F | Bounded Figure 3.5.5 sizing or exact sourced product rating; Table 3.5.2 downpipe selection; count/catchment checks; front bead, back gap and slot overflow |
| `csiro_eaves_gutter_research` | Martin 1973 Eqs 1-3, Table 2 | Historical slope, bend and outlet-position factors, required gross area, supplied product selection and half-area downpipe estimate |
| `box_gutter_design`, `rainhead_design`, `box_side_overflow`, `box_high_capacity_overflow` | 3.7, Appendix H | Exact Appendix I anchors and bounded conservative chart envelopes; unsupported chart contexts require traceable readings. Actual pipe family and H.3 gutter/rainhead depths are checked |
| `box_gutter_hydraulics` | Manning/critical depth | Independent uniform-flow diagnostic with explicit freeboard; does not replace H.1 |
| `csiro_1973_box_gutter`, `csiro_1973_rainhead` | Martin 1973 Eqs 4-8 | Historical rectangular water-section and circular receiver estimates, with explicit Imperial-to-SI conversion |
| `pervious_runoff_coefficient`, `design_flow` | 5.4.6-5.4.8 | Australian pervious soil/multiplier branches and weighted plan-area runoff |
| `open_channel_capacity`, `channel_capacity`, `channel_design` | 5.4.9 | Manning capacity/normal depth, rectangular/asymmetric trapezoidal/triangular sections, surface width, velocity, supplied floor/freeboard checks |
| `pipe_capacity`, `pipe_design`, `pipe_network`, `pipe_network_csv` | 5.4.11 | Colebrook-White full-pipe capacity, theoretical/catalogue bore, design-flow velocity, converging graph propagation, individual node rainfalls, invert and supplied endpoint cover checks |
| `charged_pipe`, `charged_pipe_system` | Darcy-Weisbach/Colebrook | Steady full-pipe energy balance, supplied minor losses, head/flow solution, series bores, hydraulic-grade and endpoint pressure checks |
| `sag_pit_capacity` | 5.4.10.1 | Sag inlet perimeter/blockage and ponding through 0.12 m |
| `roof_spreader_sheet_flow`, `valley_gutter_manning_check` | General hydraulic models | Supplied spreader sheet geometry/losses; valley geometry, normal/critical depth, explicit wave and freeboard allowances. These are not CFD |
| `valley_gutter_standard_selection` | 3.6, Table 3.6.2 | Verified small-catchment table. Automatic Figure 3.6.2 selection above 20 m2 is guarded because the supplied 2025 figure is inconsistent with physical monotonicity |
| `pumped_storage` | 8.3.6 | 10% AEP/120-minute volume, 30-minute pumping, wet-well minima; pump capacity is an input |
| `detention_orifice_capacity`, `detention_weir_capacity`, `detention_routing`, `detention_storage_sizing` | General outlet/continuity equations | Supplied coefficients and stage curves, rectangular tanks, hyetographs/losses, bypass, overflow, volume balance and multi-event plan-area search |
| `rainfall_selection`, `csv_import`, `calculation_pack` | Workflow | Exact supplied rainfall records, explicit Australian event defaults, strict CSV, fresh result records and hashes, HTML/PDF |

## Project inputs and units

Area is m2, rainfall is mm/h, flow is L/s, storage is m3 and channel dimensions are m. Pipe and gutter dimensions explicitly use mm. Gradients are rise/run: enter 0.005 for 1:200. Catalogue pipe sizes must be **internal bores**, not nominal outside diameters. Roughness is absolute k in mm; kinematic viscosity is m2/s. Manning n, outlet coefficients and minor-loss coefficients are separate quantities.

Supply project location/rainfall records, catchment boundaries, wind-direction geometry, product ratings and bores, surface/invert levels, roughness, losses, tailwater, rainfall temporal patterns and authority criteria. The rainfall selector does not retrieve BOM IFD or calculate time of concentration. The network passes supplied design flows through a converging graph; it does not calculate travel-time-dependent storm intensity, route an unsteady network, solve surcharge/backwater, or invent flow splits at bifurcations.

## Source issue: valley Figure 3.6.2

The supplied 2025 figure plots increasing allowable design rainfall as catchment area increases for a fixed effective width. That would increase permitted hydraulic loading with area, contrary to conservation-based capacity. The licensed 2018 and 2021 editions were checked: both limit this general method to 20 m2 and contain the table, without the new graph. No applicable 2025 correction file was found in the provided standards folder on 14 October 2026.

The package implements the verified table and provides separate hydraulic checks for larger valleys. It does not silently reverse, fit or reinterpret the inconsistent graph. A publisher-verified correction is required to enable automatic selection from that figure. The CFD/performance method described by RGD is not recovered in the supplied client scripts and is not claimed here.

## Remaining project/design limits

Appendix H envelopes are conservative graph selections. H.1 retains unadjusted depth without gradient reduction; H.3 uses actual pipe families and adverse gutter/rainhead-depth brackets; overflow readings disclose their allowances. Unsupported chart ranges and product-specific data require sourced inputs. General diagnostics do not establish Appendix H compliance. CSIRO's 1973 research is historical, including its original geometry assumptions and empirical factors; it is not a current-standard compliance path.

Authority OSD criteria, complete storm selection, blockage/emergency scenarios, culverts/on-grade inlet procedures, soil/site suitability, downstream receiving conditions, pump selection/controls, structural design, materials/installation, other standards and NCC checks require separate project assessment. Charged-system results assume full pipes and steady water flow; air locking, priming, siphonic initiation and transients are outside the model. Floor clearance is evaluated only from supplied levels; pipe cover is checked at supplied endpoints.
