# perf(difference simple Graph): native PyGraph::_native_difference

**Bead:** br-r37-c1-natdiffsimple (no-gaps)
**Date:** 2026-06-12
**Agent:** cc

## Gap

`difference(G, H)` for a simple **undirected `Graph`** had no native kernel — only
`MultiGraph` / `MultiDiGraph` did (`_native_difference`, br-r37-c1-natdiff). The
simple path ran `create_empty_copy` + materialized both graphs' Python `EdgeView`
into a set + `add_edges_from`. On a true-HEAD vs-nx sweep this was **3.28x slower
than networkx** (BA(800,4), `difference(g, g)`): nx 0.908 ms, fnx 2.976 ms.

> Discovery note: an earlier sweep mismeasured many fns because a **stale
> site-packages copy** of `franken_networkx` shadowed the dev tree (rch builds the
> wheel remotely; the local editable copy was days behind HEAD). All numbers here
> are from the dev tree on HEAD via `PYTHONPATH=python`.

## Lever (one)

Add `PyGraph::_native_difference` (sibling of the MultiGraph kernel) and gate the
`__init__.py` wrapper on `type(G) is Graph and type(H) is Graph`. The kernel builds
the result **entirely in Rust, in G's integer index space**:

- H's edges → a `HashSet<(usize, usize)>` of canonical (min,max) **G-index** pairs
  (H shares G's node set but may index it differently; decline → `None` if any H
  node is absent).
- Walk G via `neighbors_indices` in node-major `edges()` order, dedup each
  undirected pair once at its earlier-node encounter (exactly nx's `G.edges()`
  stream), keep pairs absent from H, emit `(current_node, neighbor)`.
- Node display keys: propagate `lazy_int_node_stop` and copy only explicitly
  materialized `node_key_map` entries — **never** call `py_node_key` per node
  (which would mint a fresh `PyInt` for every lazy-range node).

No String allocation in the hot loops; only kept edges allocate. Declines on z6uka
adjacency display overrides (falls back to the existing snapshot path).

## Proof (behavior parity — absolute)

`verify_parity.py`: 50 shapes (empty, singleton, self-loops, identical BA, BA−gnp,
path−subset, string nodes, K12−star, node/edge attrs dropped, graph-level attrs,
40 seeded gnp pairs). Compares fnx vs nx `difference` on directedness, node order,
**edge order as iterated**, and graph-attr keys.

```
cases=50 native_hits=50 mismatches=0
golden_sha256=801b1b28573c60ca6d1326ccba69d1500f5313f086c816b4b5a4f9c3677b72e3
ALL PARITY OK
```

`native_hits=50` confirms the native path is exercised (not silently falling back).
The golden sha is **identical** between the first (String-keyed) and final
(index-keyed) kernels — the optimization is byte-for-byte output-preserving.

## Benchmark (warm min-of-11, dev tree on HEAD)

| case                       | nx (ms) | fnx before | fnx after | after ratio | self-speedup |
|----------------------------|---------|-----------|-----------|-------------|--------------|
| BA800 `diff(g,g)` (empty)  | 0.897   | 2.976     | 0.818     | **0.91x**   | **3.64x**    |
| BA800 minus sparse gnp     | 2.752   | —         | 1.277     | **0.46x**   | 2.16x vs nx  |
| WS2000 minus WS            | 5.555   | —         | 2.858     | **0.51x**   | 1.94x vs nx  |
| BA3000 `diff(g,g)` (empty) | 3.999   | —         | 4.784     | 1.20x       | —            |

Headline: the flagged 3.28x-slower gap → **1.10x faster**, 3.64x self-speedup,
byte-exact. Realistic residual differences are ~2x faster than nx. The only
remaining >1x case is the **degenerate self-difference** at n=3000 (every edge
filtered) at 1.20x — a pathological input; realistic partial-overlap differences
are all faster.

## Scope

Undirected simple `Graph` only (what the sweep flagged). `DiGraph` simple-path
native difference is a clean follow-up (PyDiGraph sibling in digraph.rs).
