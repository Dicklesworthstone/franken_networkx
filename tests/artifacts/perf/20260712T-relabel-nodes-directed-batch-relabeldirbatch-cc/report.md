# br-r37-c1-relabeldirbatch — relabel_nodes_directed batch-insert (with attrs)

Status: **SHIP.** 2.14x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`relabel_nodes_directed(g, mapping)` (fnx-algorithms) — the DiGraph analog of `relabel_nodes`: copies each
edge with remapped endpoints and attrs via a per-edge `add_edge_with_attrs`.

## The lever

Collect the remapped edges as `(new_left, new_right, attrs)` tuples and insert with one
`DiGraph::extend_edges_with_attrs_unrecorded`.

## Byte-identical argument

`extend_edges_with_attrs_unrecorded` (DiGraph) dedups on the directed `(source, target)` key and merges
attrs (`existing.extend`, fnx-classes/src/digraph.rs) exactly as `add_edge_with_attrs`, and handles
self-loops. So a node-**merging** mapping (two labels → one) that collapses distinct directed edges into a
duplicate — or into a self-loop — is reproduced byte-identically. Verified: A/B parity
`assert_eq!(edges_ordered_borrowed + nodes_ordered)` for **both** a bijection and a merging mapping
(`i → "m{i/2}"`) on complete-digraph K20; the existing `test_relabel_nodes_directed_preserves_node_attrs`
suite test passes against the batch. The `RELABELDIR_BATCH_AB` marker + test name were confirmed present
(fresh binary).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib relabel_nodes_directed_batch_ab -- --ignored --nocapture`

complete-digraph K50, bijection rename (50 nodes, 2450 directed edges). 61 rounds. Ratio = base/cand, **>1
= batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **2.1437x** | 61/61 | [1.8972, 2.3502] |
| `NULL_batch_vs_batch` | 1.0035x | 33/61 | [0.9026, 1.1937] |

Decisive: candidate p5 (1.90) ~1.6x above the NULL p95 (1.19); all 61 rounds won. Smaller than the dense
result-builders because relabel is `|E|`-bounded — the win is the per-edge policy record folded to one.

## Clippy note

My change is clippy-clean (0 findings in production 39895-39925 / test 67541-67670, grep-verified). The
crate has ~12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `relabel_nodes_directed`.
- Test-only: `relabel_nodes_directed_batch_ab` A/B.

## Vein status

Eleventh fnx-algorithms result-builder batch. Next: `convert_node_labels_to_integers` (relabels to ints —
may already delegate to relabel_nodes), `power`, and more per-edge `add_edge(_with_attrs)` result-builders.
