# Box gutters and rainheads

## AS/NZS 3500.3:2025 Appendix H

The Appendix H procedures use design graphs. Automatic support combines exact Appendix I readings with conservative bounded graph envelopes. Unsupported chart contexts require sourced designer readings with their figure and geometry; no fitted RGD equation is used.

- H.1 supports 200–600 mm width curves and sampled flows from 3 L/s through 16 L/s (the domestic 200 mm curve ends at 10 L/s). It selects the next higher flow and narrower width, and retains the larger unadjusted depth without taking a gradient reduction. Exact 1:200 Appendix I readings remain available. These envelopes deliberately oversize some gutters.
- H.3 water-depth envelopes use the actual named circular or rectangular pipe family, with a bounded flow range for each family. Equal-area pipes are not substituted. The length lookup uses adopted rainhead depth `hr` (80–440 mm) and the next higher gutter-depth curve `ha` (100–170 mm). It does not use gutter depth as the rainhead-depth axis. The exact I.1 reading is ha=140 mm, hr=250 mm, length=185 mm.
- H.4 distinguishes exact downpipe families and adds a 20 mm visual-reading allowance. Its whole-flow samples stop inside each plotted pipe-family extent. H.6 and H.8 select adverse flow/width samples and disclose their visual-reading allowances. Widths and flows outside their supported ranges are rejected, rather than extrapolated. Source/context and conservative selection are retained in the result.

The sparse readings are conservative design envelopes, not exact interpolation. Licensed graph images and source pages are excluded. For tighter dimensions, supply traceable readings from the licensed graph or an appropriate product source.
`box_gutter_hydraulics` is a separate Manning normal/critical depth diagnostic. It is not a replacement for H.1 sizing. The H.3 length lookup uses adopted rainhead depth (`selected_depth_mm`, or the calculated minimum depth if omitted) as its ordinate and the actual H.1 gutter depth (`gutter_depth_at_1_in_200_mm`) to select the chart curve. The Appendix I example checks cover the box-gutter, rainhead, side-overflow, and high-capacity-overflow arithmetic. For H.7, when the weir crest offset is greater than 60 mm, the sump depth datum is above the box-gutter sole: its signed elevation below the sole is `60 mm - offset`. Sump bottom elevation is then that signed datum plus the selected sump depth.

## Historical CSIRO equations (1973)

Two chart-free estimates are provided separately from Appendix H:

- `csiro_1973_box_gutter` applies K.G. Martin, *Roof Drainage*, CSIRO DBR Technical Paper (Second Series) No. 1 (1973), pp. 7-9, Eqs. (4)-(6). It converts SI inputs to the published imperial units, evaluates the outlet flow area `f`, depth `f/w` for a rectangular water section, and estimated flow. For sloping area, the caller supplies the factor `n` read from the paper's Figure 3; it defaults to 1 for plan area.
- `csiro_1973_rainhead` applies the paper's circular receiver Eqs. (7)-(8), switching from weir to orifice relation at `H_D/D = 1/3`, then reports estimated receiver depth using `H_D = 0.6 × receiver depth`. It reports the one-diameter side-clearance recommendation when the caller supplies the clearance.

These are historical research methods, not an AS/NZS 3500.3:2025 compliance method, and their output does not establish design suitability. Confirm original assumptions, geometry, units, downstream capacity, and applicable current requirements independently. The Appendix H chart-input methods remain available for current-standard procedures.
