# Detention outlets and level-pool routing

These tools provide explicitly parameterized hydraulics and conservation-based detention routing. They do not select an authority's design storm, allowable discharge, OSD conditions, blockage allowance, outlet coefficient or required freeboard, and do not assert universal council OSD compliance.

## Outlet capacities

`run_orifice_capacity` uses `Q = Cd A sqrt(2 g H)`. The discharge coefficient is required from a documented outlet detail or test basis; gravity defaults to 9.80665 m/s². When tailwater is present, the caller must supply a submerged coefficient and the model uses differential head. This simplified model rejects tailwater at or above the upstream head. Approach velocity, vortexing, partial blockage and non-steady behavior are not included.

`run_weir_capacity` uses `Q = C L H^(3/2)`. The required coefficient convention is m^(1/2)/s. Submerged operation requires a separate supplied coefficient. Applying this free-flow power law to differential head is a caller-specified approximation, not a universal drowned-weir law. The named weir shape does not provide an implicit coefficient.

## Routing

`run_detention_routing` converts each supplied constant-intensity rainfall block to runoff with `Q = A C max(i-loss, 0)/3600`, where rainfall and loss are mm/h, area is m² and Q is L/s. It routes the controlled inflow using Modified Puls continuity and trapezoidal outlet integration. Supply a stage-storage curve, or a constant-area rectangular tank's plan area and bottom/top stages (converted to a two-point curve). Curves are piecewise linear; stage must increase strictly and storage/discharge must not decrease. Storage starts at zero. A stage-discharge curve, when supplied, is the total outlet law; otherwise configure an orifice or weir. `allowable_discharge_lps` is checked against peak total site discharge, including bypass and overflow. It does not throttle a passive outlet. `flow_control_limit_lps` may be supplied only to model a physical regulating device. The router limits integrated outflow at a dry boundary to available water and reports any volume-limited correction.

Each hyetograph block is held constant for its stated duration, including when a block ends partway through a routing step. Routing is limited to 100,000 steps per event. Stage-storage volume must increase strictly with stage so the storage curve remains invertible; stage-discharge curves may be flat. Detention sizing event names must be unique.

`bypass_fraction` and `bypass_flow_lps` represent flow that bypasses the detention storage. The output distinguishes rainfall inflow, bypass, controlled inflow, outlet and overflow. An overflow relation uses the supplied coefficient in `Q = C L H^(3/2)` and must start below the top of the stage-storage curve so the overflow can be routed within the tabulated storage range. Routing fails if the supplied curve is exceeded. Freeboard is only evaluated when positive and when the corresponding level lies on the supplied curve. Reported storage selection is a routed peak for the supplied event, not a generalized design storm.

`run_detention_storage_sizing` runs bounded bisection on the plan area of a rectangular tank with caller-supplied tank depth, freeboard, outlet law, allowable discharge and one or more design hyetographs. It reports the smallest plan area within the requested area tolerance that satisfies both the usable-storage level and total site discharge criterion for every event. An optional maximum plan area bounds the search. Results apply only to the supplied events and hydraulic assumptions; this is not an authority-specific OSD prescription.

All rainfall, runoff coefficients, loss rates, initial conditions, curves, permissible discharge and outlet data are project inputs. Use appropriately small time steps and repeat at finer steps to establish numerical convergence for the project hydrograph. Check complete-event volume balance, downstream tailwater, blockage, emergency overflow, structural/installation conditions, authority requirements and independent design criteria.

## Example

```python
from opencalcs_as3500.storage_routing import run_detention_routing

result = run_detention_routing(inputs)
```

The returned metadata keeps the package-wide standard-compliance flags false. This is a general hydraulic calculation aid; detention design provisions may come from local authority manuals and project approvals outside AS/NZS 3500.3.
