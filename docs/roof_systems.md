# Roof catchments and eaves gutter systems

These calculations implement selected AS/NZS 3500.3:2025 methods. They do not
assess full-standard compliance, rainfall selection, roof geometry survey,
system layout, thermal movement, workmanship, or building-code requirements.

## Roof catchments

`stormwater.as3500.roof_catchment_plan` accepts multiple geometry components
and groups their calculated areas by `catchment_id`, so separate gutter or
downpipe catchments remain distinct. It uses the tabulated roof-slope factor
from Table 3.4.3.2 (for fractional degrees it takes the next steeper listed
degree), the partial-exposure expression in 3.4.3.2(3), adjacent-roof
expression in 3.4.3.3, and vertical-wall expressions in 3.4.4.1–3.4.4.3.
Wind-sensitive components are evaluated together by direction before any
governing value is selected. With no explicit direction vectors, the module
uses two common signed scenarios across all components; it never adds each
component's independent maximum. If orientations differ, provide each
wind-sensitive component with `wind_scenarios` containing the same
`direction_id` values and direction-specific vertical areas. Results include
scenario totals, the governing direction overall, and a governing direction
for each `catchment_id`. Vertical wall areas may include an
`exposed_wall_height_m`; when supplied, the calculation limits their
contributing area to the corresponding 10 m height, as permitted by the note
to 3.4.4.3. Without a supplied height the entered area is used as provided.

Inputs to the partial-exposure case use the standard's order
`[Av1, Av2, Av3, Av4]`. Each entry is a separate component, allowing multi-plane
roofs to be split into the relevant drainage catchments. The calculator does
not infer windward/leeward geometry from a building model: assign the relevant
vertical areas to the terms shown in the standard's figure and trial the
governing wind signs.

## Eaves gutters and downpipes

`stormwater.as3500.eaves_gutter_chart` uses conservative numeric readings of
the dual flow/effective-area axes in Figures 3.5.5(A)/(B) to size the
effective gutter area per vertical downpipe. Inputs include total catchment,
rainfall, gradient, and the proposed number of downpipes. It divides the total
catchment equally among those downpipes, reports flow and catchment per pipe,
and checks the Table 3.5.2 downpipe selection. Between
digitized flow ticks, it uses the next higher tick as an upper bracket; it does
not interpolate between sparse readings. The chart's assumptions
apply: about 2:1 effective width-to-depth ratio, least-favourable bends and
downpipe position, and the listed gutter shapes. The rainfall domain is
bounded to 50–500 mm/h and the flow domain to the plotted axes; it rejects
extrapolation. Appendix G.2's 51 m² at 145 mm/h check gives 2.054 L/s and
7,300 mm² on Figure 3.5.5(A); this implementation uses the conservative 8,500 mm²
upper tick bracket for that input. The chart requirement is reported separately
from the adopted area used for the Table 3.5.2 lookup. This sizing output is an effective area, not a
product profile recommendation; confirm product geometry, brackets, and
manufacturer data before selection.

`stormwater.as3500.eaves_gutter_system` checks the Clause 3.5 inputs, chooses
the matching Table 3.5.2 downpipe entry, computes the theoretical minimum
downpipe count from total area and the supplied area-per-downpipe rating, and
checks each supplied subcatchment against that rating. The standard's
Figures 3.5.5(A)/(B) are plotted design charts. No curve equation has been
derived from them here. Instead, enter an exact manufacturer rating for the
selected effective gutter area, rainfall intensity, and gradient, and cite
the product chart in `source`. Exact equality is required; interpolation and
extrapolation are not performed. The example rating illustrates the input
shape and is not a product recommendation or a licensed-standard value.

The selected gradient band is `1:500 and steeper` at a numeric gradient of at
least 0.002; lower values use the flatter-than-1:500 table column. Gutter
effective cross-sectional area must be established from the product geometry
and Clause 3.5.5. It is not calculated from a nominal profile name.

Table 3.5.2 selection enforces its listed lower and upper effective-area
bounds. Its final two rows have no circular downpipe size; the result reports
those as rectangular/square-only selections instead of fabricating a circular
size.

### Historical CSIRO eaves-gutter method

`stormwater.as3500.csiro_eaves_gutter_research` implements K.G. Martin,
*Roof Drainage*, CSIRO Division of Building Research Technical Paper (Second
Series) No. 1 (1973), printed pages 2 and 5–7: flow-load Eq. (1), rounded
eaves-gutter Eq. (2), required-area Eq. (3), and the slope/bend/outlet
coefficients in Table 2. It converts the paper's ft², in/h, imperial gal/min,
and in² units explicitly. The coefficient `0.00757` in Eq. (3) is retained as
printed; Eq. (1)'s separate flow-load coefficient `0.0087` is also reported.
The source does not reconcile that difference in the printed text.

The Table 2 inputs are the published gutter-slope condition, bend-to-outlet
distance band, and outlet position. Rectangular gutters receive the paper's
10% area increase. The paper states that the downpipe area should be one half
of the selected gutter area. An optional product catalog lets the calculation
select the smallest entered gross area meeting the required area; if a
gradient and each product's Clause 3.5 effective area are also supplied, the
current Table 3.5.2 downpipe selection is returned separately. These results
are historical research calculations, not current-standard compliance or
product certification. Manufacturer profile data remain user-supplied.

## Overflow

`stormwater.as3500.eaves_overflow` calculates Appendix F.2 inflow as
`Ac × R / 3600` L/s, which represents all downpipes fully blocked under the
1% AEP overflow event, then checks capacity against that flow. It supports:

- front bead at least 10 mm below fascia: 1.5 L/s/m (F.4.4);
- back gap using exact Table F.1 combinations of listed head and average gap
  (F.4.2); and
- slots using the F.4.3 equation with entered slot area, head, and discharge
  coefficient (default 0.61).

Appendix F applies to eaves gutter catchments up to 400 m². This method only
checks the selected overflow measure's hydraulic capacity. It does not check
roof/building interactions or detailed device placement. Appendix F's
continuous-device freeboard margin is reported as 3 mm for gradients steeper
than 1:500 and 6 mm otherwise; verify that the installed device provides it.

## Source and verification

Source reviewed: AS/NZS 3500.3:2025 Clauses 3.4.3–3.4.4, 3.5.2–3.5.5, Appendix G.2, and
Appendix F, especially F.2–F.4. Calculations have independent numeric cases in
`validation/roof_systems_benchmarks.json`; examples are input-shape examples,
not a substitute for project-specific manufacturer data. The scanned CSIRO
paper was reviewed visually from its printed pages; no scan or OCR text is
included in this package.
