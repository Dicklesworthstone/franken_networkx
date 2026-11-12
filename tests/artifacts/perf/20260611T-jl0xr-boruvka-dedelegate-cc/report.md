# br-r37-c1-jl0xr — minimum/maximum_spanning_edges algorithm='boruvka'

## Problem
`minimum_spanning_edges(G, algorithm="boruvka")` delegated to nx via a full
`_fnx_to_nx` conversion — **1.40–1.60x slower than nx**.

## Root cause (cProfile)
The conversion was only ~20% of the cost. nx's `boruvka_mst_edges` calls
`nx.edge_boundary` once per component per pass (~70k calls at n=1500). Because
franken_networkx is registered as an nx backend, **every one of those calls
pays the full `@nx._dispatchable` backend-dispatch wrapper plus an
`EdgeDataView` construction** — that dispatch/view machinery dominated.

## Lever (one)
De-delegate: reimplement nx's Borůvka in-process over a plain adjacency
snapshot (one cheap native `fnx_to_nx_adjacency` crossing), with the edge
boundary inlined as a tight loop — no nx graph build, no per-call dispatch,
no views. Reuses the *real* `networkx.utils.UnionFind` over the fnx node
objects so component grouping (`to_sets`), set iteration order and union
tie-breaks are bit-identical; best-edge uses nx's exact strict-`<`
first-wins rule over the same iteration order (node-set order ×
adjacency-insertion order). NaN / non-numeric weights bail to nx so the exact
error message is preserved.

Pure-Python change in `python/franken_networkx/__init__.py`
(`_boruvka_spanning_edges_inproc` + branches in `minimum_spanning_edges` and
`maximum_spanning_edges`). No Rust changes.

## Result (interleaved min-of-N, same host window)
| case        | before (delegate) | after (in-proc) | nx     | self-speedup | after vs nx |
|-------------|-------------------|-----------------|--------|--------------|-------------|
| n1500 deg8  | 63.08 ms (1.60x)  | 19.03 ms        | 39.37  | 3.32x        | 0.48x (2.1x faster) |
| n3000 deg8  | 153.48 ms (1.56x) | 48.19 ms        | 98.73  | 3.19x        | 0.49x (2.0x faster) |

## Proof
- Golden sha256 over yielded edge stream: **before == after == nx**, identical
  at both sizes (`proof.json`).
- `proto_transcription.py`: 420 cases (sizes/seeds × min/max + string/tuple
  node keys) vs nx on native nx graphs — 0 fails.
- `parity_sweep.py` fair contract (fnx vs nx on the converted fnx graph,
  incl. heavy-tie & unit weights, disconnected forests, data=True/False,
  NaN raise + ignore_nan, MST graph form) — 0 fails.
- `tests/python/test_spanning_tree_conformance.py` + 4 MST suites: 272 passed.
