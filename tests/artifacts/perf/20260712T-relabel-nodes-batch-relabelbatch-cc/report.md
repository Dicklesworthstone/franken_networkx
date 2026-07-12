# br-r37-c1-relabelbatch — relabel_nodes batch-insert (with attrs)

Status: **SHIP.** 2.13x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`relabel_nodes(graph, mapping)` (fnx-algorithms) copies each edge with remapped endpoints and its attrs,
inserting via a per-edge `add_edge_with_attrs` (a policy record each).

## The lever

Collect the remapped edges as `(new_left, new_right, attrs)` tuples and insert with one
`Graph::extend_edges_with_attrs_unrecorded`.

## Byte-identical argument

`extend_edges_with_attrs_unrecorded` **dedups** on the canonical endpoint pair and **merges** attrs
(`existing.extend(attrs)`, fnx-classes/src/lib.rs:1487) exactly as `add_edge_with_attrs`, and handles
self-loops (`left == right`). So a node-**merging** mapping (two labels → one) that collapses distinct
edges into a duplicate — or into a self-loop — is reproduced byte-identically, in the same order. Verified:
A/B parity `assert_eq!(edges_ordered_borrowed + nodes_ordered)` for **both** a bijection mapping and a
merging mapping (`i → "m{i/2}"`) on K20; the 3 existing `test_relabel_nodes_*` suite tests (mapping,
preserves-node-attrs undirected + directed) all pass against the batch.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib relabel_nodes_batch_ab -- --ignored --nocapture`

K60 bijection rename (60 nodes, 1770 edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **2.1256x** | 61/61 | [1.6582, 2.8498] |
| `NULL_batch_vs_batch` | 0.9976x | 29/61 | [0.8605, 1.2106] |

Decisive: candidate p5 (1.66) above the NULL p95 (1.21); all 61 rounds won. Smaller than the dense
result-builders because relabel is `|E|`-bounded — the win is the per-edge policy record folded to one bulk
insert. (Note: the first A/B run hit a stale rch test binary — 0 tests matched — so this was re-run to
confirm the `RELABEL_BATCH_AB` marker + test name appear.)

## Clippy note

My change is clippy-clean (0 findings in production 39845-39875 / test 67408-67540, grep-verified). The
crate has ~12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `relabel_nodes`.
- Test-only: `relabel_nodes_batch_ab` A/B.

## Vein status

Tenth fnx-algorithms result-builder batch. Confirms `extend_edges_with_attrs_unrecorded`'s dedup+merge is
byte-identical even for node-merging relabels. Next: `relabel_nodes_directed` (near-clone), `power`.
