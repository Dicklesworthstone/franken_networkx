# br-r37-c1-gnmbatch — gnm_random_graph integer-seen dedup + batch-by-index

Status: **SHIP.** 8.55x, byte-identical. clippy clean.

## The target

`gnm_random_graph(n, m, seed)` (fnx-generators) is a rejection sampler: draw a random pair, reject
self-loops and DUPLICATES, until `m` distinct edges land. The duplicate check read the graph
(`graph.has_edge(&node_labels[u], &node_labels[v])` — a per-candidate 2×name→index hash + tuple
lookup) and each accepted edge did `graph.add_edge(node_labels[u].clone(), node_labels[v].clone())`
(2 String clones + 2 name hashes + policy record).

## Profile-first (the barabasi lesson applied)

Per the barabasi finding (batch wins only for INSERTION/DEDUP-bound generators, not sampling-bound),
I checked gnm's split: its sampling is two CHEAP `rng.choice_index` draws per candidate, while the
`has_edge` dedup + `add_edge` insertion are the EXPENSIVE String-keyed operations. So gnm is
insertion/dedup-bound → a batch candidate (confirmed: 8.55x, decisive).

## The lever

Track accepted edges in an integer `seen: HashSet<(usize,usize)>` (canonicalized `(min,max)` exactly
as `has_edge`'s `canon_pair`) instead of reading the graph, then batch-insert with
`Graph::extend_existing_index_edges_unrecorded`. Drops the per-candidate String hashing + the per-edge
clones/hashes/policy.

## Byte-identical argument

`has_edge(node_labels[u], node_labels[v])` canonicalizes via `canon_pair(u,v)=(min,max)` (node index
== label index), so `seen.contains((min(u,v),max(u,v))) ≡ has_edge` — the rejection decision is
identical, hence the `choice_index` draw sequence and the accepted edge set/order are identical. The
batch `(u,v)` matches `add_edge`'s adjacency push order and name-order endpoint canonicalization; nodes
pre-exist, no self-loops, unique edges. Verified in-test:
`assert_eq!(new.edges_ordered_borrowed(), old.edges_ordered_borrowed())` + `nodes_ordered`.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib gnm_batch_ab -- --ignored --nocapture`

n=2000, m=50000. 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **8.5547x** | 61/61 | [2.6116, 12.9688] |
| `NULL_batch_vs_batch` | 0.9782x | 22/61 | [0.7117, 1.1545] |

Decisive: candidate p5 (2.61) above the NULL p95 (1.15); all 61 rounds won.

## Gates

- A/B `cargo test --release`: GNM_BATCH_AB present (not stale); parity `assert_eq!` green.
- gnm tests incl. `gnm_random_graph_matches_networkx_seeded_example` (exact-vs-nx): green.
- Full fnx-generators suite / clippy `-D warnings`: green/clean (see validation.log).

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `gnm_random_graph`.
- Test-only: `gnm_batch_ab` A/B.

## Vein status

Second engine-level generator batch win (after gnp 13.20x). Confirms the refined rule: batch wins for
insertion/dedup-bound generators (gnp dense, gnm rejection-with-String-has_edge), not sampling-bound
(barabasi). Next filtered candidates: `complete_multipartite_graph`, dense `watts_strogatz`;
`gnm_random_digraph` (directed twin — needs a DiGraph index-batch inserter).
