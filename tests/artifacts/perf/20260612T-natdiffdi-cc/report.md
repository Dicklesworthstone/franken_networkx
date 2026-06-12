# perf(difference simple DiGraph): native PyDiGraph::_native_difference

**Bead:** br-r37-c1-natdiffsimple-di (no-gaps) — directed sibling of br-r37-c1-xi2nh
**Date:** 2026-06-12 · **Agent:** cc

## Gap

`difference(G, H)` for a simple **directed `DiGraph`** had no native kernel — only
`MultiDiGraph` did. The simple path ran `create_empty_copy` + Python `EdgeView` set
+ `add_edges_from`, **1.36x slower than networkx** (gnp(800, 0.02) directed): nx
9.71 ms, fnx 13.95 ms. (Numbers from the dev tree on HEAD via `PYTHONPATH=python` —
the site-packages copy is stale; see reference_stale_install_benchmark_trap.)

## Lever (one)

Add `PyDiGraph::_native_difference` (directed sibling of `PyGraph::_native_difference`,
shipped 90a402435) and gate the `__init__.py` wrapper on
`type(G) is DiGraph and type(H) is DiGraph`. Builds the result entirely in Rust in
G's integer index space:

- H's directed edges → `HashSet<(usize, usize)>` of (source, target) **G-index**
  pairs (no min/max — orientation matters; decline → `None` if any H node absent).
- Walk G via `successors_indices` in node-major `edges()` order (each directed edge
  appears once in its source's out-row), keep pairs absent from H, emit (u, v).
- Node display keys: copy `node_key_map` entries only (never per-node `py_node_key`).
- No String allocation in the hot loops; declines on z6uka succ/pred display
  overrides (falls back to the snapshot path).

## Proof (behavior parity — absolute)

`verify_parity.py`: 49 directed shapes (empty, self-loops, orientation-sensitive,
gnp pairs, identical→empty, string nodes, node/edge attrs dropped, graph attrs, 40
seeded gnp pairs). Compares fnx vs nx on directedness, node order, **edge order**,
graph-attr keys.

```
cases=49 native_hits=49 mismatches=0
golden_sha256=37dcb9dfd084bedfde5749928eaf9ca617193b99659c2bd0012e0996b137dcb0
ALL PARITY OK
```

`native_hits=49/49` confirms the native path is exercised.

## Benchmark (warm min-of-11, dev tree on HEAD)

| case                  | nx (ms) | fnx before | fnx after | after ratio | self-speedup |
|-----------------------|---------|-----------|-----------|-------------|--------------|
| gnp800 minus gnp      | 9.954   | 13.95     | 4.435     | **0.45x**   | **3.14x**    |
| gnp800 self (empty)   | 2.037   | —         | 1.388     | 0.68x       | 1.47x vs nx  |
| gnp2000 minus gnp     | 31.748  | —         | 14.948    | **0.47x**   | 2.12x vs nx  |
| gnp2000 self (empty)  | 6.307   | —         | 5.118     | 0.81x       | 1.23x vs nx  |

Headline: 1.36x-slower → **2.2x faster** than nx; 3.14x self-speedup, byte-exact.
Unlike the undirected case, the directed kernel is faster across **all** cases
including the degenerate self-difference (no min/max canonicalization overhead).

## Scope / follow-up

Simple `DiGraph` only. Remaining operator construction-tax gaps (all same lever):
`symmetric_difference` simple Graph/DiGraph (~1.4-1.7x), `intersection` (~1.2x).
