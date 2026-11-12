# br-r37-c1-clvit1 — `closeness_vitality_single` full-index integer BFS

Status: **SHIP.** 5.85x median self-speedup, byte-identical.

## The target

`closeness_vitality_single(graph, node)` — O(V·(V+E)) — computes the Wiener-index
delta from removing one node by BFSing from every remaining node in the induced
subgraph. It is on the live Python path: the pyo3 `closeness_vitality` wrapper calls
`fnx_algorithms::closeness_vitality_single` when a `node` argument is supplied. The
old kernel built a `HashMap<&str, usize>` (`node_to_idx`) over the remaining nodes
and, per BFS pop, called `graph.neighbors(remaining_nodes[u])` (a fresh `Vec<&str>`
alloc) then re-hashed each neighbour name.

## The lever

The identical transform applied to `closeness_vitality` (br-r37-c1-clvit): snapshot
integer adjacency ONCE (`Vec<&[usize]>`), mark the excluded index `ex`, and BFS over
full node indices skipping `ex`. `node_to_idx` eliminated; `ex` comes from
`graph.get_node_index(node)?` (which also replaces the `has_node` guard).

## Byte-identical argument

Same as clvit: full-index order agrees with subgraph-index order (`nodes_ordered()`
minus `ex`), so the `(fs, fv)` pairing `fv > fs` is preserved; every non-`ex`
neighbour is a remaining node; the BFS queue discipline + adjacency order are
unchanged; `subgraph_wiener` is a sum of integer distances (`< 2^53`, exact) →
order-independent AND identical; `full_wiener - subgraph_wiener` exact;
disconnection → `NEG_INFINITY` preserved. Verified in-test:
`assert_eq!(closeness_vitality_single, baseline)` on the n=200 graph passed, and the
existing `closeness_vitality_single_node_api` unit test (path 0-1-2: v0=3.0,
v1=−∞, absent=None) is green.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib closeness_vitality_single_clvit1_ab -- --ignored --nocapture`

Well-connected graph (spanning path + random edges to ~deg-10), n=200, excluding a
middle node. 61 rounds. Ratio = base/cand, **>1 means integer-BFS faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **5.8503x** | 61/61 | [4.7105, 6.5809] |
| `NULL_int_vs_int` | 1.0091x | 38/61 | [0.8508, 1.1845] |

The lever median (5.85x) clears the NULL floor: candidate p5 (4.71) is ~4x above the
NULL p95 (1.18), and every one of 61 paired rounds won. This completes the
closeness-vitality family (both the full and single-node kernels are now integer).

## Gates

- clippy `-D warnings` (remote): clean.
- `closeness_vitality_single_node_api` unit test: green.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `closeness_vitality_single`.
- Test-only: `closeness_vitality_single_orig_string` baseline + `..._clvit1_ab` A/B.
