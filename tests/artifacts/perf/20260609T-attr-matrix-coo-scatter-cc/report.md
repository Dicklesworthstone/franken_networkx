# perf(attr_matrix): vectorised native-COO scatter for the common case

br-r37-c1-attrmtxcoo

## Problem
`attr_matrix(G, edge_attr=None|"weight")` (node_attr=None, simple graph) built
the dense matrix by (a) materialising per-edge attr DICTS via to_edgelist_simple
(~8ms @1500 edges) and (b) a Python per-edge loop with scalar `M[i,j] += value`
(~8ms). ~2x slower than nx.

## Lever (one)
For the common case (node_attr=None, simple Graph/DiGraph, edge_attr None or
"weight"), read native f64 COO arrays in the rc/node ordering via
`adjacency_nodelist_typed_arrays` (remaps endpoints to the ordering; no per-edge
dicts) and scatter vectorised with `np.add.at`. attr_matrix's M is float64
(np.zeros default) unless dtype is pinned — no int/float inference needed; the
undirected COO is already symmetric. Other cases (callable/named edge_attr,
node_attr, multigraph) keep the existing loop.

Touched: python/franken_networkx/__init__.py (attr_matrix fast path).

## Proof (behavior-preserving)
Fast path == the existing general path (callable edge_attr bypasses the fast
gate) over 80 cases (Graph/DiGraph, weighted) — 0 mismatches (M + ordering).
vs nx: identical except the PRE-EXISTING normalized zero-degree-row divergence
(fnx guards rs[rs==0]=1 -> 0; nx does unguarded M/=rowsum -> nan) which the
existing fnx loop also has. pytest -k "attr_matrix or attr or matrix": 2783
passed. ATTRM_SHA c19a2aa66c63bc457390aeae2e7b7f66662590e93bd68fdb619c13d9deb3bf43.

## Timing (warm min-of-6, BA n=1500 m=5, edge_attr="weight")
nx 10.05ms, fnx before 12.5ms, fnx after 3.79ms => ~2x slower (small-n it
sweeps 2.1x) -> 2.6x FASTER than nx, ~3.3x self-speedup.

## Score
Impact: high (3.3x self-speedup, 2x slower -> 2.6x faster). Confidence: high
(0/80 vs general path, 2783 tests). Effort: low (reuses the typed COO binding).
Score >> 2.0.
