# min_weighted_vertex_cover: drop fnx->nx conversion, native integer kernel

Bead: `br-vcnative`.

## Catastrophe
`fnx.approximation.min_weighted_vertex_cover` resolved through the generic
`_ApproximationNamespace.__getattr__` wrapper, which round-trips the graph through
`_networkx_graph_for_parity` (an O(n^2) fnx->nx conversion) and then runs nx's
pure-Python local-ratio loop over the slow fnx EdgeView/NodeView. Warm min-of-N:
fnx 11x / 16.7x / 28x SLOWER than networkx at n=200/600/1500 (gap GROWS with n).
A fast Rust kernel existed but was never used by the namespace, AND it diverged
from nx on weighted graphs (node-order `<` string dedup vs nx edge order: 73/120).

## Lever (one)
1. Rust kernel rewritten to replicate nx's edge-order local-ratio greedy EXACTLY:
   walk the integer adjacency (`neighbors_indices`), process pair (u,v) only when
   index `u <= v` -- nx's by-node-position dedup + orientation, including self-
   loops. `weight=None` => unit weights (nx ignores node "weight" attrs then).
   Pure integer: no per-node neighbor-Vec alloc, no string-keyed cost map.
2. Binding simplified: pass `weight` Option through; drop an unused PyDict build.
3. Native `_ApproximationNamespace.min_weighted_vertex_cover` calls the kernel
   directly (no conversion). DiGraph inputs (nx iterates directed edges) delegate.

## Isomorphism / golden proof
250 graphs (unweighted / weighted / weight=None-with-attrs / self-loops /
directed): set-identical to networkx, golden sha256 PASS (1d97da2c...).
Python test (6/6): tests/python/test_min_weighted_vertex_cover_native_parity.py.

## Benchmark (undirected, gnp p=0.02, warm min-of-5)
    n      nx        fnx        ratio
    200    0.11ms    0.03ms     0.23x (fnx FASTER)
    600    0.52ms    0.09ms     0.18x
    1500   2.61ms    0.27ms     0.10x
    3000   9.66ms    0.63ms     0.06x  (fnx 15x FASTER)
From 28x SLOWER to 15x FASTER, margin grows with n. Score >> 2.0.

## Files
- crates/fnx-algorithms/src/lib.rs: min_weighted_vertex_cover kernel + tests.
- crates/fnx-python/src/algorithms.rs: binding.
- python/franken_networkx/__init__.py: native namespace method.
