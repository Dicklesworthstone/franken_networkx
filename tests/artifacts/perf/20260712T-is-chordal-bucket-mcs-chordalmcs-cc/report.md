# br-r37-c1-chordalmcs — is_chordal: O(V²) MCS → O((V+E)·log V) weight-bucket MCS

Status: **SHIP.** 9.40x on a 6000-node interval graph, byte-identical, clears the STRICT gate. An
ALGORITHMIC-COMPLEXITY win (not a micro-opt) — the ratio grows with |V|.

## The target

`is_chordal(graph)` runs a Maximum Cardinality Search (MCS) to build a perfect elimination order, then checks
the PEO. The MCS was **O(|V|²)**: every one of the |V| rounds did a full linear scan
`(0..n).filter(|i| !numbered[i]).max_by_key(|i| (weight[i], Reverse(i)))` to find the max-weight unnumbered
node. On large graphs this quadratic scan dominates the whole function.

## The lever

Replace the per-round full scan with a **weight-bucket** structure: `buckets[w]` (a `BTreeSet<usize>`) holds
the still-unnumbered nodes whose current weight is `w`. Each round descends to the highest non-empty bucket
(max weight) and pops its first element (`BTreeSet` → smallest index). A weight bump moves a node
`buckets[wt] → buckets[wt+1]`. Total work: O(|E|) bucket moves × O(log|V|) + O(|V|+|E|) `max_w` descents =
**O((|V|+|E|)·log|V|)**.

Also folded in: the adjacency build now reads `edges_storage_order_index_iter()` (index-native) instead of
materialising `edges_ordered()` (a `Vec<EdgeSnapshot>`: 2 owned Strings + AttrMap clone per edge) + an
`idx`-map name→index rehash. `adj` is a `Vec<HashSet<usize>>` (order-independent) and `nodes_ordered()`
position == internal node index, so the indices are identical → byte-identical.

## Byte-identical argument

The bucket MCS makes the **identical selection** as the old scan: highest non-empty bucket = max weight; the
`BTreeSet`'s first element = min index — exactly `max_by_key((weight, Reverse(i)))` (max key ⇒ max weight; for
equal weight, max `Reverse(i)` ⇒ min i). Weight updates are unchanged, so the elimination `order` is identical
→ same PEO → same result. `max_w` is always ≥ every unnumbered node's weight (it only rises on an increment),
so the descent never underflows while nodes remain. Verified: the A/B asserts `old_fn(&g) == super::is_chordal(&g)`
(full inline O(V²) version vs the shipped one) on a 6000-node interval graph; **all 8 production chordal suite
tests pass** (cliques path/star/triangle/cycle4, cycle graph, treewidth path/star/non_chordal).

## Median A/B (full function, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib is_chordal_mcs_ab -- --ignored --nocapture`

Large SPARSE chordal graph (6000-node 4th-power-of-a-path interval graph) so the O(V²) MCS dominates and
`is_chordal` runs fully (chordal → no early exit). 61 rounds. Ratio = old-scan / bucket, **>1 = bucket faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BUCKET_vs_scan` | **9.3968x** | 61/61 | [7.8244, 11.2900] |
| `NULL_bucket_vs_bucket` | 1.0001x | 31/61 | [0.8530, 1.2087] |

Decisive: candidate **p5 (7.82) is ~6.5x above the null p95 (1.21)** — clears the STRICT gate by a wide
margin; all 61 rounds won; null perfectly centred on 1.0. Because the win is O(V²)→O((V+E)logV), the ratio
GROWS with |V| (9.4x at 6000 nodes; larger for bigger graphs).

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `is_chordal` (MCS + adjacency build).
- Test-only: `is_chordal_mcs_ab` A/B.

## Vein status

NEW LEVER TYPE for this session: an O(V²) naive "linear-scan-for-max each round" inside an otherwise-linear
graph algorithm → weight/priority buckets for O((V+E)logV). Sweep for the same antipattern (a `for _ in 0..n`
loop whose body does `(0..n).filter(...).max_by_key/min_by_key(...)`) in other kernels: greedy orderings,
MCS/lex-BFS variants, degeneracy/k-core orderings, priority-driven selection.
