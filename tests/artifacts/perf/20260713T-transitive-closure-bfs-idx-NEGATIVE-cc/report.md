# br-r37-c1-tcidx — transitive_closure per-source BFS String→int — REJECT (diluted + unmeasurable)

Status: **REJECT / REVERTED.** Byte-identical and strictly-better in isolation, but the full-function win is
diluted below a very noisy null. Documented so peers don't re-attempt the BFS-only conversion.

## What was tried

`transitive_closure` runs a per-source BFS keyed on `HashSet<&str> visited` + `successors_iter` — the same
String→int multi-round shape that won 32x on `girth`/`voterank`. Converted the BFS to an epoch-stamped
`Vec<u32>` over `successors_indices` (byte-identical: same reachable set + same source-major discovery order →
same edge sequence). Verified the edge SET matches (assert) + `transitive_closure_{chain,empty,hardened}` +
`transitive_closure_batch_ab` pass.

## Why it's a REJECT

Unlike girth/voterank (where ALL the work was the String-keyed loop and the output was a scalar), most of
`transitive_closure`'s time is the **`extend_edges_unrecorded` batch insertion of O(|V|²) closure edges** —
which itself resolves each `(&str,&str)` to indices (String hashing) AND is allocation-heavy. The per-source
BFS is only a small fraction, so converting it barely moves the total. Worse, the allocation-heavy insertion
makes the timing extremely noisy.

Full-function A/B (chain DAG 800 → ~320k closure edges), 61 rounds:

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INDEX_vs_string` | 1.2803x | 51/61 | [0.7184, 2.1953] |
| `NULL_index_vs_index` | 0.9325x | 27/61 | [0.5876, 1.9484] |

The candidate median (1.28) does **not** clear the null p95 (1.95); the A/A null is enormous ([0.59, 1.95],
median 0.93) — the extend/alloc variance drowns the ~1.28x BFS signal. Not a shippable measured win.

## What WOULD unlock it (deferred)

The dominant String hashing is in `extend_edges_unrecorded((&str,&str))`, not the BFS. DiGraph has NO
index-based edge extend (Graph has `extend_existing_index_edges_unrecorded`, DiGraph does not — only
`extend_edges_unrecorded<Into<String>>`). Adding an index-pair extend to DiGraph (fnx-classes) and emitting
`(source_idx, w_idx)` would remove that half too — THEN the combined int conversion could clear the bar. That
is a fnx-classes change (separate lever), not attempted here.

## Lesson

A multi-round String→int conversion only wins big when the String-keyed loop is the DOMINANT cost. When the
function ALSO does an O(output) String-hashing/allocation step (here the O(|V|²) edge materialization +
insertion), the per-source-BFS conversion is Amdahl-diluted AND the alloc noise makes it unmeasurable. CHECK
the output-construction cost before converting a per-source BFS whose result is a large String-keyed
structure (transitive_closure, transitive_reduction, all_pairs_shortest_path_length are this shape). Contrast
scalar-output BFS (girth/wiener) where the loop IS the function → 32x.
