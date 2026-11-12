# Perf WIN — edge_boundary(data=False, nbunch2=None) G.neighbors fast path: 0.78x -> 1.41-1.66x (br-r37-c1-ebneigh)

- Agent: `BlackThrush` · 2026-06-21 · File: `__init__.py`
- Second application of the br-aspneigh lever (G.edges -> G.neighbors, ~8x cheaper).

## The gap
edge_boundary's hot branch (`type(G) in (Graph, DiGraph)`) built `G.edges(nset1, data=...)`
and filtered by XOR — but for the common `data=False` case it only needs the neighbor, and
the EdgeView materializes (u,v) tuples (~8x the cost of G.neighbors). 0.78x vs nx.

## The fix
For `data is False and nbunch2 is None`, emit `(u, v) for u in nset1 for v in G.neighbors(u)
if v not in nset1` (an edge is in the boundary iff exactly one endpoint is in nset1; with u
always in nset1 the XOR reduces to `v not in nset1`). Build eagerly + `yield from` (per-item
generator yield costs ~0.4us/edge and erased the win in a first attempt). SAME nset1-set x
adjacency iteration order -> byte-identical to nx. nbunch2-given and data=True keep the
EdgeView path. (A first edit targeted an unreachable post-`_coerce_nbunch` branch — the real
hot path is the exact-type branch; corrected.)

## Verify
- BYTE-IDENTICAL vs nx 2500/2500 incl nbunch2-given + data=True variants, self-loops,
  directed, string nodes. pytest -k boundary 530 passed.

## MEASURED (nx/fnx, warm min)
| nbunch1 size | before | after |
|--------------|--------|-------|
| 50           | 0.78x  | 1.41x (68us) |
| 150          | 0.78x  | 1.66x (145us) |
