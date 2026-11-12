# bipartite.minimum_weight_full_matching de-dispatch — 4x slower → 1.26x (3.4x self)

Bead: br-r37-c1-n4dwd
Agent: cc / 2026-06-14

## Problem

`fnx.bipartite.minimum_weight_full_matching` was re-exported from networkx
(`@nx._dispatchable`), so calling it on an fnx graph round-tripped the WHOLE
graph through `_fnx_to_nx` (O(V+E)) before nx split the bipartite sets, built the
biadjacency matrix, and deferred to `scipy.optimize.linear_sum_assignment`. ~4x
slower than nx (delegated 2.65ms vs nx 0.62ms on gnmk 150×120/1200).

## Fix (run nx's exact algorithm in-process, no conversion)

nx's algorithm is exactly: `sets()` → `biadjacency_matrix(rows=U, cols=V)` →
inf-pad → `scipy linear_sum_assignment` → map indices back. Both `sets` and
`biadjacency_matrix` are already fnx-native and byte-exact, and the SciPy LAP
solver is deterministic — so the whole thing runs in-process on the fnx graph
with no fnx→nx conversion:

```python
left, right = sets(G, top_nodes)          # fnx-native, byte-exact
U, V = list(left), list(right)
ws = biadjacency_matrix(G, row_order=U, column_order=V, weight=weight, format="coo")
weights = np.full(ws.shape, np.inf); weights[ws.row, ws.col] = ws.data
d = {U[u]: V[v] for u, v in zip(*sp.optimize.linear_sum_assignment(weights))}
d.update({v: u for u, v in d.items()})
```

Byte-identical: the set split, row/column ordering, inf-padded matrix, and SciPy
assignment all match nx exactly — including when integer weights create many
optimal assignments (LAP tie-breaking is deterministic and identical). nx-typed
inputs delegate to nx.

## Proof

- 200-case parity sweep: 100 seeds × {`top_nodes` given, `top_nodes=None`} on
  complete-bipartite graphs with integer weights 1–4 (heavy ties) — **0
  mismatches** vs nx.
- `weight=None` (all-ones) matches; degenerate / no-finite-assignment behaviour
  matches (same SciPy path).
- Golden (complete_bipartite 20×25, int weights 1–9, seed=7): sorted-items
  sha256 `ae2804ccf935b573…`, equals nx.
- Targeted bipartite/matching/matrix suite: 2687 passed (1 known pre-existing
  coverage-matrix-doc failure). Full suite: only the 6 known pre-existing.

## Timing (min-of-10, gnmk 150×120/1200)

| path | time | vs nx |
|------|------|-------|
| delegated (nx-on-fnx, conversion) | 2.65ms | 4.3x |
| in-process (fnx) | 0.78ms | 1.26x |
| nx (native graph) | 0.62ms | — |

3.4x self-speedup; the conversion tax is eliminated. Residual ~1.26x is the
fnx biadjacency edges-view floor + SciPy LAP (shared with nx). Pure-Python.
