# br-r37-c1-1s6cb — route fnx.algorithms.centrality.* to optimized fnx top-level

## Problem
`networkx.algorithms.centrality` (reachable as `fnx.algorithms.centrality`,
`from franken_networkx.algorithms.centrality import X`, and `fnx.centrality`)
was aliased **verbatim to networkx's module**. So
`fnx.algorithms.centrality.betweenness_centrality(G)` ran nx's pure-Python
Brandes against the fnx graph's adjacency **views** — measured **33x slower**
than the native `fnx.betweenness_centrality` (363ms vs 11ms at n=400, p=0.04).
The top-level namespace was optimized but the canonical submodule namespace
bypassed it entirely — an inconsistency vs networkx, where
`nx.betweenness_centrality IS nx.algorithms.centrality.betweenness_centrality`.

## Lever
Add a `franken_networkx/centrality.py` shim (mirroring the existing
bipartite/operators/clique override pattern) that re-exports
`networkx.algorithms.centrality` but rebinds every name networkx itself
aliases to top level to the `franken_networkx` top-level (optimized,
parity-tested) implementation. Register it in the uncontested
`algorithms/__init__.py` (`_FNX_OVERRIDE_SUBMODULES` + module override), so
`fnx.algorithms.centrality.X IS fnx.X` exactly as `nx...centrality.X IS nx.X`.

Guard: only substitute when `getattr(networkx, name) is <submodule fn>` — i.e.
networkx re-exports it at top level — so any submodule name that collides with
a *different* top-level function (e.g. bipartite's `clustering`) is left
untouched. 43/43 centrality functions route.

No Rust change; touches only `algorithms/__init__.py` (+13 lines) and the new
`centrality.py`. The top-level `__init__.py` (peer-locked) is untouched, so
the bare `fnx.centrality` access path (without first touching `fnx.algorithms`)
is a follow-up.

## Result (n=400, p=0.04; before = previous raw-nx-submodule-on-fnx-views)
| function               | routed (fnx) | before (raw nx) | speedup |
|------------------------|--------------|-----------------|---------|
| betweenness_centrality | 11.1 ms      | 360.7 ms        | 32.5x   |
| load_centrality        | 10.6 ms      | 337.2 ms        | 32.0x   |

Other functions inherit fnx's top-level performance (closeness/harmonic/degree
already fast; subgraph_centrality/second_order/katz native). No function
regresses (routing returns the same object `fnx.X` the project already ships).

## Proof
- Routing identity: `fnx.algorithms.centrality.X is fnx.X` for all checked fns.
- Golden rounded sha256 (9 dp) over result dicts: **fnx == genuine nx** for
  betweenness/load/closeness/harmonic/degree at n=200 and n=400 (`proof.json`);
  max abs diff ≤ 1.4e-12 (= fnx top-level's existing parity tolerance;
  betweenness/closeness/degree are float-identical, maxdiff 0–1e-18).
- `tests/python -k centrality`: 1179 passed, 6 skipped, 1 xpassed, 0 failed.
