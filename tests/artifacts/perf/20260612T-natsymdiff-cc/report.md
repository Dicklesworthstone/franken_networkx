# perf(symmetric_difference simple Graph + DiGraph): native kernels

**Beads:** br-r37-c1-natsymdiff (undirected) + -di (directed), no-gaps
**Date:** 2026-06-12 · **Agent:** cc
Completes the difference-family native-kernel sweep (after br-r37-c1-xi2nh, h28tz).

## Gap

`symmetric_difference(G, H)` for simple `Graph` / `DiGraph` had no native kernel
(only `MultiGraph`/`MultiDiGraph` did). The simple path ran `create_empty_copy` +
two Python `EdgeView` sets + a two-pass `add_edges_from`. On HEAD (dev tree via
`PYTHONPATH=python`): undirected **1.36x slower**, directed **1.72x slower** than nx.

## Lever (one)

Add `PyGraph::_native_symmetric_difference` (lib.rs) and
`PyDiGraph::_native_symmetric_difference` (digraph.rs), gated by
`type(G) is Graph / DiGraph`. Build the result in G's integer index space:

- `g_set` / `h_set` of G-/H-index edge pairs (undirected: canonical (min,max);
  directed: (src,tgt)). H's nodes map into G's index space via a `&str -> usize`
  map (H may index the shared node set differently — decline → `None` if any H node
  is absent).
- **Two passes, wrapper order**: pass 1 emits G-only edges in G's node-major
  `edges()` order; pass 2 emits H-only edges in H's node-major `edges()` order.
  Walking H in H's own node order makes the per-pass emission byte-match
  `H.edges()` regardless of the index space used for the dedup/membership key.
- Node display from G (`create_empty_copy(G)` semantics): copy `node_key_map` +
  propagate `lazy_int_node_stop` (undirected); never per-node `py_node_key`.

No String allocation in the hot loops; declines on z6uka display overrides.

## Proof (behavior parity — absolute)

`verify_parity.py`: 71 shapes across BOTH directedness — empty, identical→empty,
self-loops, orientation-sensitive, string nodes, attrs dropped, graph attrs, and 60
seeded sweeps where **H's node insertion order is reversed** (G-index ≠ H-index, the
adversarial case for the cross-index mapping). Compares fnx vs nx on directedness,
node order, **edge order**, graph-attr keys.

```
cases=71 native_hits=71 mismatches=0
golden_sha256=7529f4d66a7628254c55eaf7b5d926695de3daa84f85916d21bb689277467267
ALL PARITY OK
```

## Benchmark (warm min-of-11, dev tree on HEAD)

| case                | nx (ms) | fnx before | fnx after | after ratio | self-speedup |
|---------------------|---------|-----------|-----------|-------------|--------------|
| u_BA800 sym gnp     | 5.364   | 7.59      | 2.769     | **0.52x**   | **2.74x**    |
| u_WS2000 sym WS     | 7.652   | —         | 4.476     | 0.58x       | 1.71x vs nx  |
| d_gnp800 sym gnp    | 14.033  | 27.22     | 7.091     | **0.51x**   | **3.84x**    |
| d_gnp2000 sym gnp   | 55.399  | —         | 32.542    | 0.59x       | 1.70x vs nx  |

Headline: 1.36x/1.72x slower → **1.7-2.0x faster** than nx, byte-exact;
self-speedup 2.74x (undirected) / 3.84x (directed).

## Follow-up

`intersection` (~1.22x) is the last operator on this lever.
