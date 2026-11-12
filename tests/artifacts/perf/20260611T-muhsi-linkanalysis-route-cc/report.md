# br-r37-c1-muhsi (part 2) — route fnx.algorithms.link_analysis to fnx top-level

## Problem
`networkx.algorithms.link_analysis` (reachable as `fnx.algorithms.link_analysis`,
`fnx.link_analysis`, and the `from ... import X` path) was aliased verbatim to
networkx's module. `pagerank` / `hits` already reached the fnx backend via nx's
dispatch (neutral), but `google_matrix` ran nx's pure-Python dense matrix build
against the fnx graph's adjacency views — ~2x slower than the native
`fnx.google_matrix`.

## Lever
Add a `link_analysis.py` shim (identical pattern to the shipped `centrality.py`
/ `distance_measures.py`) that rebinds each name networkx aliases to top level
(`getattr(nx,name) is submodule_fn` guard) to the `franken_networkx` top-level
implementation, registered in the uncontested `algorithms/__init__.py`. Result:
`fnx.algorithms.link_analysis.X IS fnx.X` exactly as `nx...link_analysis.X IS
nx.X`. No Rust change.

## Result (warm, isolated; before = previous raw-nx submodule path on H)
| function      | routed (fnx) | before (raw nx) | speedup |
|---------------|--------------|-----------------|---------|
| google_matrix | 7.85 ms (n=1000) | 15.49 ms     | 1.97x   |
| pagerank      | 0.33 ms      | 0.39 ms         | 1.18x   |
| hits          | dispatch-neutral (already fast)     | —       |

Modest but real, drop-in-consistency + perf, no regression.

## Proof
- Routing identity: `fnx.algorithms.link_analysis.X is fnx.X` for pagerank /
  hits / google_matrix; `from franken_networkx.algorithms.link_analysis import
  google_matrix` routes; child module `pagerank_alg` still importable.
- Golden sha256 over results: **fnx == genuine nx** for pagerank / hits /
  google_matrix at n=500 and n=1000 (`proof.json`), all `sha_match: true`.
- `tests/python -k "pagerank or hits or google_matrix or link_analysis"`:
  225 passed, 6 skipped, 1 xpassed, 0 failed.

## Note on the submodule-routing vein
This completes the high-value submodule routing (centrality 32x,
distance_measures 7-16x, link_analysis ~2x). The remaining sibling submodules
(components / dag / clique / cuts / flow) are **dispatch-neutral** — their
functions already reach the fnx backend via nx's dispatcher when given an fnx
graph (clique.find_cliques even regresses if routed), so routing them yields no
win. The genuinely deep remaining target is the dense-LAPACK current-flow
family (`approximate_current_flow_betweenness` — bead br-r37-c1-wz3sy, target
~12x by using fnx's native Laplacian-inverse instead of nx's scipy dense
inverse), which lives in the peer-locked `__init__.py`.
