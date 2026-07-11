# br-r37-c1-hknhararybatch — hkn_harary_graph batch-by-index edge insertion

Status: **SHIP.** 19.86x, byte-identical. clippy clean.

## The target

`hkn_harary_graph(k, n)` builds the Harary graph H(k,n): a k-regular circulant (edges `(node,
(node+shift)%n)` for `shift in 1..=k/2`) plus, for odd k, a diameter matching (`(node, node+n/2)`).
It is **dense** (kn/2 edges). The native builder used per-edge
`add_edge(node_labels[left].clone(), node_labels[right].clone())`; all nodes pre-exist
(`graph_with_n_nodes`). Deterministic (no RNG) → insertion-bound.

## The lever

Collect the `(left, right)` INDEX pairs in the SAME order (per-shift circulant, then the matching) and
batch-insert with `Graph::extend_existing_index_edges_unrecorded`. Drops per accepted edge: 2 String
clones + 2 name→index hashes + 1 runtime-policy record.

## Byte-identical argument (no dedup needed)

- **Circulant, no duplicates/self-loops.** Every shift `s` satisfies `1 <= s <= k/2 < n/2` (because
  `n >= k+1`), so `2s != n` for all shifts. Hence for a fixed shift the loop `for node in 0..n`
  emits `n` *distinct* undirected edges, each exactly once (edge `{a, a+s}` is only produced at
  `node=a`, since `node=a+s` would require `2s ≡ 0 (mod n)`), and none is a self-loop (`s != 0`).
- **Matching, distinct from circulant.** The odd-k matching uses shift `n/2`, which strictly exceeds
  every circulant shift `k/2 < n/2` → no overlap. For even n it emits `{node, node+n/2}` for
  `node in 0..n/2` (all distinct); for odd n it emits `{node, (node+n/2)%n}` for `node in 0..=n/2`,
  all distinct (distinct smaller endpoint) with no wrap.

So every produced pair is unique with no self-loop → the batch (which does not dedup) is byte-identical
to the per-edge `add_edge` (whose simple-Graph dedup is never triggered).
`extend_existing_index_edges_unrecorded` canonicalizes endpoints by name-order and pushes `adj_indices`
exactly as `add_edge`; edges collected in the identical order. Verified:
- A/B cross-branch parity: `assert_eq!(edges_ordered_borrowed + nodes_ordered)` of batch vs per-edge
  for **6 configs** — (200,2000) even-k/even-n, (5,50) odd-k/even-n, (5,51) odd-k/odd-n, (4,1001)
  even-k/odd-n, (1,100) k=1 path, (2,3) tiny — all pass.
- Suite exact-vs-nx: `hkn_harary_graph_connectivity_one_matches_path_graph` (k=1) and
  `hkn_harary_graph_odd_connectivity_odd_order_matches_networkx_edges` (odd-k/odd-n) both pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib hkn_harary_batch_ab -- --ignored --nocapture`

H(200, 2000) (2000 nodes, 200000 edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **19.8551x** | 61/61 | [14.5986, 24.0025] |
| `NULL_batch_vs_batch` | 1.0233x | 38/61 | [0.8350, 1.2380] |

Decisive: candidate p5 (14.60) ~11.8x above the NULL p95 (1.24); all 61 rounds won. Highest-magnitude
generator batch win to date (dense k-regular → node creation is a tiny fraction).

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `hkn_harary_graph`.
- Test-only: `hkn_harary_batch_ab` A/B.

## Vein status

Eleventh engine-level generator batch win (gnp 13.20x, gnm 8.55x, complete_multipartite 13.24x, turan
16.22x, ring_of_cliques 19.94x, windmill 18.63x, caveman 3.86x, barbell 16.92x, lollipop 13.29x,
tadpole 7.10x, hkn_harary 19.86x); barabasi 1.04x surfaced (sampling-bound). Next: `hnm_harary_graph`,
`generalized_petersen_graph`, ladder/grid family (all deterministic per-edge, now that sparse also wins).
