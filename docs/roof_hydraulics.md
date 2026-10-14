# Roof spreader and valley-gutter hydraulic diagnostics

These functions are transparent hydraulic checks, not proprietary solver reproductions and not standalone roof-drainage designs.

## Roof spreader

`run_roof_spreader` computes the upper and lower effective catchment areas independently using the freely exposed sloping-roof factor `1 + 0.5 tan(slope)`, then calculates upper flow, local lower-roof flow and combined lower discharge. It checks a caller-supplied spreader width/depth using Manning's equation for a rectangular sheet with supplied surface slope, run length, roughness and spreader drop. The drop adds to the energy slope as `drop/run`. A supplied minor-loss coefficient reduces capacity through the energy balance `S_eff = S + drop/run - K V²/(2gL)`, solved iteratively for capacity. The required width at the supplied depth is also solved using the exact rectangular hydraulic radius for this model.

This sheet-flow idealization does not establish uniform spreader distribution, validate the physical spreader detail, assess receiving-gutter capacity or implement AS/NZS 3500.3 Clause 3.4.5 (the 2025 clause heading is “Higher catchment area”).

## Valley gutter

`run_valley_gutter` derives idealized cross-valley side slopes from the two supplied roof pitches and their plan angle, then calculates the asymmetric trapezoidal flow section, Manning capacity, normal depth and critical depth at the supplied design flow. The check also reports design flow from supplied contributing plan area and rainfall intensity, effective sheet width after a supplied obstruction, and the explicit caller-supplied wave allowance and freeboard. It reports a rectangular open-channel screening width at the same flow depth as a possible alternate concept; this is not a box-gutter design or a standard selection.

This is a Manning diagnostic only. It is not CFD-equivalent and does not implement the AS/NZS 3500.3 Clause 3.6 general sizing method. The 2025 standard's method uses effective-width Table 3.6.2/Figure 3.6.2, a 12.5 degree minimum roof pitch, and a nominal valley side angle of 16.5 degrees (1:3.4). No 35 degree maximum roof pitch is applied. Catchment chart limits, sheet detailing, obstructions and other installation constraints need separate evaluation. A positive caller wave allowance is required and is never inferred. The function reports hydraulic section checks, not complete adequacy.

## Higher catchment area

`run_higher_catchment` calculates each roof's effective sloping catchment and combined flow to the lower roof drainage system. For a spreader discharge it checks the 1,800 mm treated strip on both sides and the material detail: tiled roofing must be sacked to the eaves per AS 2050, while corrugated-metal side laps must be sealed along their full length. Supplied lower-gutter/downpipe or rainhead/sump capacities are compared with the combined flow. The output flags that overflow still needs assessment. This is a Clause 3.4.5 screening tool, not a complete compliance check.

## Standard valley selection

`run_standard_valley_selection` selects sheet width, effective depth and effective width from Australian Table 3.6.2 for catchments up to 20 m². Table rainfall rows are inclusive: at a shared boundary the matching row is selected. Required total gutter depth is effective depth plus 15 mm freeboard. The AU selection uses 5-minute rainfall, a 12.5 degree minimum roof pitch, and the nominal 16.5 degree valley side angle (1:3.4); no 35 degree maximum is stated by the source. The Figure 3.6.2 path above 20 m² remains guarded because the 2025 chart's apparent rising DRI-versus-area curves are inconsistent with older editions' 20 m² table limit. The output optionally compares supplied dimensions and flags roof-slope, nominal side-angle and obstruction conditions. It does not select site rainfall or establish full compliance.

## Example

```python
from opencalcs_as3500.roof_hydraulics import (
    run_higher_catchment,
    run_roof_spreader,
    run_standard_valley_selection,
    run_valley_gutter,
)
```
