# br-r37-c1-koutmdgbatch — random_uniform_k_out_multidigraph batch (keyed)

Status: **SHIP.** 1.63x (modest), byte-identical. clippy clean. First MultiDiGraph keyed-batch win.

## The target

`random_uniform_k_out_multidigraph(n, k, self_loops, seed)` gives each source `k` out-edges to targets
sampled **with replacement** — so the same `(source, target)` can recur, producing **parallel edges** with
MultiDiGraph auto-assigned keys. The native builder did per-edge `add_edge_with_attrs`, and
`add_edge_impl` pays **two** `record_decision` (policy) calls per edge.

## The lever

Reproduce the auto-key with a per-`(source, target)` counter and batch via
`MultiDiGraph::extend_keyed_edges_with_attrs_unrecorded` (one policy record for the whole batch). This is
a **String-keyed** inserter (it still resolves node names), so it only drops the per-edge policy records,
not the name hashing → a modest win.

## Byte-identical argument (including keys)

`add_edge_impl` computes the auto-key as `edges.get((u,v)).map_or(0, |b| b.len())`, then bumps it while
that key is occupied. In this generator every edge is auto-keyed with no gaps, so the bucket always holds
keys `0..len-1` and the assigned key is exactly `len` — i.e. a per-`(u,v)` sequential counter `0, 1, 2, …`.
The batch reproduces that with a `HashMap<(usize,usize), usize>` counter, emitting keyed edges in the same
source-major / draw order. **Verified profile-first** (before the production edit): `kout_mdg_batch_ab`
parity asserts across 4 configs — `(50,5,false)`, `(50,20,true)` (self-loops, dense → many parallel edges
with keys > 0), `(200,50,false)`, `(1000,500,false)` — all `assert_eq!(edges_ordered_borrowed +
nodes_ordered)` pass (`edges_ordered_borrowed` on MultiDiGraph includes the key). Suite exact-vs-nx:
`random_uniform_k_out_multidigraph_matches_networkx_seeded_example` and `…_respects_self_loop_filter` pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib kout_mdg_batch_ab -- --ignored --nocapture`

random_uniform_k_out_multidigraph(1000, 500) (1000 nodes, 500000 directed multi-edges). 61 rounds. Ratio =
base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **1.6342x** | 61/61 | [1.4269, 1.9003] |
| `NULL_batch_vs_batch` | 1.0129x | 34/61 | [0.9019, 1.1553] |

Decidable: candidate p5 (1.43) is above the NULL p95 (1.16); all 61 rounds won. Modest because the keyed
inserter is String-based (only the 2 per-edge policy records are dropped; name hashing stays); a future
index-based MultiDiGraph keyed inserter would push this higher.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `random_uniform_k_out_multidigraph`.
- Test-only: `kout_mdg_batch_ab` A/B.

## Vein status

Twenty-fourth engine-level generator batch win; first MultiDiGraph keyed-batch — proves the per-`(u,v)`
counter reproduces MultiDiGraph's auto-key byte-identically (vs nx), enabling future MultiDiGraph batch
levers. This closes the last plausibly-batchable directed generator; `random_k_out_graph`
(mutable-weight rewire) and RNG-sampling-bound generators remain out of scope.
