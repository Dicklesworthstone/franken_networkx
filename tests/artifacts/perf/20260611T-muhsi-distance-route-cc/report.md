# br-r37-c1-muhsi (part 1) — route fnx.algorithms.distance_measures to fnx top-level

## Problem
`networkx.algorithms.distance_measures` (reachable as
`fnx.algorithms.distance_measures`, `fnx.distance_measures`, and the
`from franken_networkx.algorithms.distance_measures import X` path) was aliased
verbatim to networkx's module. Most distance functions (center/diameter/
radius/periphery/eccentricity) already reached the fnx backend via nx's
dispatch, but `harmonic_diameter` and `kemeny_constant` did **not** — they ran
nx's pure-Python all-pairs computation against the fnx graph's adjacency
*views*: `harmonic_diameter` 746ms, `kemeny_constant` 1041ms on the submodule
path.

## Lever
Add a `distance_measures.py` shim (identical pattern to the shipped
`centrality.py` / existing `structuralholes.py`) that re-exports nx's submodule
but rebinds each name networkx itself aliases to top level
(`getattr(nx,name) is submodule_fn`) to the `franken_networkx` top-level
(optimized, parity-tested) implementation. Registered in the uncontested
`algorithms/__init__.py`. Result: `fnx.algorithms.distance_measures.X IS fnx.X`,
exactly mirroring `nx...distance_measures.X IS nx.X`.

No Rust change; touches only `algorithms/__init__.py` (+`distance_measures` in
the override set, +8-line registration) and the new `distance_measures.py`.

## Result (n=600, p=0.02; before = previous raw-nx submodule path on H)
| function          | routed (fnx) | before (raw nx) | speedup | vs genuine nx |
|-------------------|--------------|-----------------|---------|---------------|
| harmonic_diameter | 96.7 ms      | 745.7 ms        | 7.7x    | 7.7x          |
| kemeny_constant   | 66.8 ms      | 1041.0 ms       | 15.6x   | 5.2x          |

center/diameter/radius/periphery/eccentricity/barycenter are **neutral** on
the submodule path (already dispatched to the fnx backend) but become
consistently the fnx top-level surface (14-16x faster than genuine nx). No
function regresses.

## Proof
- Routing identity: `fnx.algorithms.distance_measures.X is fnx.X` for all 8 fns.
- Golden sha256 over results: **fnx == genuine nx** for center/diameter/
  eccentricity/harmonic_diameter/kemeny_constant at n=200 and n=600
  (`proof.json`), all `sha_match: true`.
- Parity sweep (8 fns × 120 connected graphs) fnx top-level vs genuine nx: 0
  fails.
- `tests/python -k "distance or eccentric or diameter or barycenter or kemeny
  or harmonic_diameter"`: 1470 passed, 0 failed.
