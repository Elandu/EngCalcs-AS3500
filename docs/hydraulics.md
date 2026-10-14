# Pipe and channel hydraulics

These runners provide bounded calculations for AS/NZS 3500.3:2025 Clause 5.4.9 (open channels), Clause 5.4.11.2 (full-flow pipe sizing), and cited installation checks. Results retain `full_standard_compliance=false` and `standard_compliance_evaluated=false`; the calculations do not establish whole-standard or project compliance.

## Channels

`channel_capacity` evaluates Manning flow at a supplied flow depth. `channel_design` solves normal depth for a rectangular, symmetric/asymmetric trapezoidal, or triangular channel by bisection, then reports wetted area, surface width, mean velocity, and optional freeboard/floor clearance. Manning roughness and gradient are inputs. When bed and floor/dampcourse levels are supplied, the runner reports the 300 mm clearance check from Clause 5.4.9(e). Freeboard is checked only against the user-supplied value.

## Pipes

Pipe capacity and selection use full circular flow, Colebrook-White Darcy friction with the laminar `64/Re` relation, and user-supplied kinematic viscosity and roughness `k` in mm. Selection considers only internal bores supplied by the caller; it does not infer nominal-to-internal diameter from a catalogue. The default velocity limit is 2.0 m/s. The 1.5 m/s outlet value is reported as the Clause 5.4.11.2 recommendation.

Friction is interpolated continuously between the laminar limit at Re = 2,300 and Colebrook at Re = 4,000; this is an explicit approximation within the uncertain transition region. Selection checks velocity at the design flow and reports both the capacity-only and velocity-only theoretical minimum bore before selecting a supplied catalogue bore.

The network runner propagates node inflows over a connected acyclic directed graph. It detects duplicate/missing IDs, disconnected components, cycles, non-falling or inconsistent invert grades, inadequate capacity, velocity-limit exceedance, and cover inconsistencies. `required_cover_m` is a project criterion supplied by the caller; no universal minimum cover is assumed because Clause 6.2.5 depends on pipe material and installation location. Bore changes at junctions are reported for project review.

Each node can supply local inflow and catchments with their own rainfall intensities. The runner reports outlet flows and a conservation residual. Branches may converge; bifurcations are rejected because no hydraulic split rule is assumed. Endpoint surface levels establish the cover checks. Network travel times, storm selection, unsteady routing, surcharge and backwater are outside this model. `pipe_network_csv` parses explicit pipe and node data, reconciles junction inverts and executes this same calculation.

## Charged pipe

The charged-pipe runner calculates Darcy-Weisbach friction head plus caller-provided minor-loss coefficients, or solves flow for a supplied available head by bisection. Optional upstream/downstream energy levels establish the head balance and must agree with any separately supplied available head.

`charged_pipe_system` solves steady flow through a series of pipes with different bores, roughness, lengths and losses. It reports energy and hydraulic-grade levels, pressure heads at supplied endpoints, the head-balance residual and supplied pressure criteria. Minor losses occur at reach ends. It excludes branching pressure networks, pump curves, transient effects, air entrainment, air locking and siphonic priming. The full-pipe assumption requires project review wherever pressures are below atmospheric.

## Provenance and limits

Formula references are AS/NZS 3500.3:2025 Clauses 5.4.9 and 5.4.11.2. Colebrook-White roughness values and velocity limits follow Clause 5.4.11.2; the applicable material value remains an input. The cover calculation uses finished surface to pipe crown and an optional project criterion. Licensed standard pages or extracts are not included.
