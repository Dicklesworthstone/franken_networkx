# br-r37-c1-gnpbatch — gnp_random_graph batch-by-index edge insertion

Status: **SHIP.** 13.20x end-to-end (31x insertion), byte-identical. clippy clean.

## The target

`gnp_random_graph(n, p, seed)` (fnx-generators) draws one `rng.random()` per node pair and, on
accept, did `graph.add_edge(node_labels[left].clone(), node_labels[right].clone())` — per accepted
edge: **2 String clones + 2 name→index hashes + 1 runtime-policy record**, even though `left`/`right`
are already node indices and all `n` nodes pre-exist (`graph_with_n_nodes`). O(|E|) of each.

## The lever

Collect the accepted `(left, right)` INDEX pairs during the RNG walk, then batch-insert with
`Graph::extend_existing_index_edges_unrecorded` (an existing index-based bulk inserter for graphs
whose nodes already exist). Drops the per-edge String clones, name hashing, and per-edge policy
records; the O(n²) RNG walk is untouched.

## Byte-identical argument

The RNG draw is independent of `add_edge`, so drawing per pair in the same order yields the identical
accepted edge set. `extend_existing_index_edges_unrecorded` canonicalizes `edge_index_endpoints` by
name-order (`left_name <= right_name`) and pushes `adj_indices[left].push(right)` /
`adj_indices[right].push(left)` in insertion order — **exactly** what `add_edge_with_attrs` does
(lib.rs:1698-1708) — and the gnp pairs are unique with pre-existing nodes, so no dedup/auto-create
divergence. The batch skips only the per-edge policy LEDGER record (the established `unrecorded`
pattern used by complement/transitive_closure) — internal telemetry, not the observable graph or
nx-parity. Verified in-test: `assert_eq!(batch.edges_ordered_borrowed(), string.edges_ordered_borrowed())`
+ `nodes_ordered` equality, for BOTH the isolated insertion AND the full end-to-end build.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib gnp_batch_ab -- --ignored --nocapture`

n=800, ~10%-dense (|E|=31920). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INSERT_batch_vs_string` (insertion only) | **31.10x** | 61/61 | [20.41, 47.84] |
| `E2E_batch_vs_string` (full gnp incl. RNG walk) | **13.20x** | 61/61 | [9.13, 16.95] |
| `NULL_batch_vs_batch` | 1.03x | 35/61 | [0.83, 1.23] |

The insertion (the lever) is 31x; the realistic end-to-end gnp is **13.20x** (the shared O(n²) RNG
walk dilutes it). Both decisive: E2E p5 (9.13) ~7x above the NULL p95 (1.23), 61/61 won.

## Gates

- A/B `cargo test --release`: GNP_BATCH_AB present (not stale); both parity `assert_eq!`s green.
- Full fnx-generators suite: green (byte-identity of the gnp change — see validation.log).
- clippy `-D warnings`: clean.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `gnp_random_graph`.
- Test-only: `gnp_batch_ab` A/B.

## Vein — same pattern in sibling generators (next candidates)

Per-edge `add_edge(labels[i].clone(), labels[j].clone())` accept loops with pre-existing nodes +
index-in-hand appear across the random generators: `gnp_random_digraph` (directed twin — needs a
DiGraph index-batch inserter), `gnm_random_graph`, `watts_strogatz_graph`, `barabasi_albert_graph`,
`newman_watts_strogatz_graph`, `powerlaw_cluster_graph`. Each is a `generator_accept_loop_batch` win.
