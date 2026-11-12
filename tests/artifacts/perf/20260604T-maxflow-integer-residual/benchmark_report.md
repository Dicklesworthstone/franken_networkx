# Edmonds-Karp residual: String-keyed hashmap -> integer-relabeled flat arrays

Bead: `br-flowint`.

## Catastrophe

`compute_max_flow_residual` -- the Edmonds-Karp core behind `maximum_flow`,
`minimum_cut`, `edge_connectivity` and `node_connectivity` -- represented the
residual network as `HashMap<String, HashMap<String, f64>>` and, on EVERY BFS
visit, collected the neighbor keys into a `Vec<&str>` and ran
`neighbors.sort_unstable()`. So each augmenting-path BFS paid String hashing,
String cloning (predecessor/visited), and an O(deg log deg) re-sort per node --
across every augmenting path, across every flow. A warm vs-nx sweep measured
`edge_connectivity` 3.3x / 4.5x / 6.7x SLOWER than networkx at n=150/300/500
(the gap GROWS with n).

## Lever (one) -- memory-layout swing

Relabel nodes to dense integer indices **in lexicographic (string) order**, so
that ascending-index neighbor iteration reproduces the original
`sort_unstable()` traversal order EXACTLY. The hot loop now runs on:
- residual as `Vec<BTreeMap<usize, f64>>` (ordered keys => no per-visit sort),
- BFS with `Vec<bool>` visited + `Vec<usize>` predecessor (no String hashing/cloning).

The string-keyed residual is re-materialized ONCE at the end so the return type
and all downstream consumers (`flow_edges_from_residual`, the min-cut reachability
BFS) are untouched. Because the augmenting-path selection, bottlenecks and
updates are bit-identical, the flow values, residual and min-cut partitions are
byte-identical.

## Isomorphism / golden proof

80 random directed+undirected capacitated graphs, max_flow_value & min_cut_value:

    golden_fnx = 6fb4252e14290f14d7b79224a75f1744db10c59db624af4d74a6250427e67db6
    golden_nx  = 6fb4252e14290f14d7b79224a75f1744db10c59db624af4d74a6250427e67db6
    VALUE ISOMORPHISM: PASS

edge_connectivity (60 graphs) + node_connectivity (40 graphs): exact match vs nx.
Python test: tests/python/test_maxflow_integer_residual_parity.py (6/6).

## Benchmark (warm min-of-4)

    edge_connectivity (gnp p=0.04 undirected):
      n      nx        fnx BEFORE          fnx AFTER
      150    0.0098s   0.0346s (3.29x)     0.0200s (2.05x)
      300    0.0425s   0.1971s (4.55x)     0.0989s (2.33x)
      500    0.1170s   0.8156s (6.72x)     0.3655s (3.12x)
    maximum_flow_value (gnp p=0.05 directed, capacitated):
      n=200  nx 0.0069s  fnx 0.0034s  (2.0x FASTER than nx)
      n=400  nx 0.0215s  fnx 0.0166s  (1.3x FASTER than nx)

The flow kernel roughly HALVES the edge_connectivity gap and makes
`maximum_flow_value` faster than networkx. Score: kernel ~2x across all flow
functions x Confidence 1.0 (exact golden) / Effort ~2 >= 2.0.

## Next lever (REPORTING RULE)

`edge_connectivity` is still ~2-3x slower because each of the |D| dominating-set
flows re-materializes the string residual, rebuilds a String-keyed
`reverse_residual`, and runs a String-sorted reachability BFS to recover a
min-cut PARTITION that `global_edge_connectivity` then DISCARDS (it only reads
`.value`). Next: a value-only max-flow path (skip residual string round-trip,
flow-dict extraction, and the partition) for the connectivity callers -- target
edge_connectivity from 3x slower to FASTER than nx.

## Files
- `crates/fnx-algorithms/src/lib.rs`: `compute_max_flow_residual` integer hot loop.
- `tests/python/test_maxflow_integer_residual_parity.py`.
