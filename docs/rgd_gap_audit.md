# RGD workflow comparison after extension

Reviewed against the user's saved investigation and decoded client files. No third-party implementation was copied. Server-side PHP solvers and the reported valley CFD solution were not present in that material.

| Previously missing workflow | Added support | Limits of equivalence |
|---|---|---|
| Complex roof/wall catchments | Grouped geometry and shared wind cases | Designer supplies signed projections and scenario correspondence |
| Eaves/downpipes | Chart sizing, source-rated products, count/catchment and table selection | Bounded figure readings and supplied product catalogue; no universal manufacturer database |
| Eaves overflow | Front bead, back gap, slots and blocked-downpipe event | Supplied geometry and design rainfall; detailing remains project-specific |
| Long gutters/CSIRO | Historical empirical factors from the user's full 1973 guide | Historical research; current standard and performance approval remain distinct |
| Box gutters/rainheads/sumps/overflows | Appendix H workflows, bounded conservative chart envelopes, example anchors, geometry, independent diagnostics | Exact interpolation/full chart coverage is not claimed; unsupported contexts need sourced readings |
| Pipe sizing/network | Colebrook capacity, theoretical bore, catalogue/velocity, branch convergence, inverts/cover, CSV | No unsteady surcharge or network travel-time/storm model |
| Channels | Asymmetric/triangular normal depth, width, velocity, freeboard and floor clearance | Uniform Manning flow; supplied roughness and levels |
| Charged pipes | Energy/flow solve and series hydraulic-grade/pressure profile | Full pipes, steady conditions, explicit losses; no priming/air model |
| Spreaders | Upper/lower accounting, standard material detail and sheet hydraulic checks | Supplied geometry and coefficients; not a CFD simulation |
| Valleys | Verified standard table plus normal/critical-depth/wave/freeboard diagnostics | Large-catchment 2025 graph guarded; RGD's CFD solver is unavailable and not claimed |
| Detention | Outlet hydraulics, level-pool routing, bypass/overflow and multi-storm tank sizing | Supplied events and authority criteria; not a universal council compliance tool |
| Rainfall | Location/AEP/duration selection and depth/intensity conversion from source records | No live BOM retrieval or embedded location/IFD database |
| Reports | Job metadata, fresh calculations, result hashes, HTML/PDF and CLI | Standalone plugin reporting; no host UI redesign or deployment |

The original saved roof-flow cases continue to agree at two decimal places. The steep-pipe record at 138.89 L/s and grade 1:2 selects a 300 mm internal bore at 1.96489156 m/s; the recovered `Tsize` field denotes theoretical diameter. These comparisons are secondary evidence, distinct from equation verification.

This extension provides tools across the identified workflow families. It does **not** establish complete RGD numerical parity, CFD equivalence, whole-standard implementation or a project compliance assessment. See [coverage](coverage.md) and [verification](verification.md) for supported methods and evidence.
