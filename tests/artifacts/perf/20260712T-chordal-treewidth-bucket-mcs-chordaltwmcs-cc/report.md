# br-r37-c1-chordaltwmcs — chordal_graph_treewidth: O(V²) String-keyed MCS → O((V+E)·log V) index-bucket MCS

Status: **SHIP.** 176.32x on a 6000-node interval graph, byte-identical, STRICT gate by a mile. Same lever as
the shipped is_chordal `chordalmcs` (9.40x) applied to `chordal_mcs_max_clique_size` (behind
`chordal_graph_treewidth`) — but ~19x BIGGER because this function was O(V²) AND String-keyed (the String
hashing compounded the quadratic scan). An algorithmic-complexity win; the ratio GROWS with |V|.

## The target

`chordal_graph_treewidth(graph)` → `chordal_mcs_max_clique_size(graph)` runs a Maximum Cardinality Search to
find the max clique size (treewidth = max_clique − 1). The MCS was **O(V²)**: each of the V rounds did a full
`remaining.iter().max_by(|l, r| labels[l].cmp(labels[r]).then(rank[r].cmp(rank[l])))` scan over all remaining
nodes — AND it was **String-keyed** (`HashSet<&str> remaining`, `HashMap<&str,usize> labels`), paying a String
hash per lookup and per neighbour increment.

## The lever (double win)

Weight-bucket MCS indexed by node index: `buckets[l]` (a `BTreeSet<usize>`) holds the remaining nodes at label
l; each round descends to the highest non-empty bucket (max label) and pops its first element (min index). A
label bump moves a node `buckets[wt] → buckets[wt+1]`. **O((V+E)·log V)**. Labels/removed are now `Vec`s indexed
by node index (`rank[name]`) — no String hashing in the peel loop.

## Byte-identical argument

The bucket selection is IDENTICAL to the old `max_by(labels.cmp().then(rank[r].cmp(rank[l])))`: highest
non-empty bucket = max label; `BTreeSet.first()` = min index; and `rank[r].cmp(rank[l])` picks min rank (== min
index) among equal labels. `rank[name]` == node index == position in `nodes_ordered()` (IndexMap
`get_index_of`). The clique-completeness check (`node_set_is_complete` over each chosen node's already-removed
neighbours) and the `NotChordal` early-return are unchanged, so `max_clique_size` — and the treewidth — are
identical. `max_label` is always ≥ every remaining node's label, so the descent never underflows.

Verified (once run): A/B asserts `old_tw(&g) == chordal_graph_treewidth(&g)` (full inline O(V²) String-MCS vs
shipped) on a 6000-node interval graph; the `test_chordal_graph_treewidth_{path,star,non_chordal}` suite tests.

## Median A/B

`cargo test --release -p fnx-algorithms --lib chordal_treewidth_mcs_ab -- --ignored --nocapture`

6000-node 4th-power-of-a-path interval graph (chordal → runs fully). 61 rounds. Ratio = old-scan / bucket,
**>1 = bucket faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BUCKET_vs_scan` | **176.3175x** | 61/61 | [127.3480, 269.2032] |
| `NULL_bucket_vs_bucket` | 1.0072x | 34/61 | [0.9141, 1.1000] |

Decisive beyond question: candidate p5 (127) is ~115x above the null p95 (1.10); all 61 rounds won; null
perfectly centred on 1.0. The ratio GROWS with |V| (O(V²)+String → O((V+E)logV)+int). All 3
`test_chordal_graph_treewidth_{non_chordal,path,star}` suite tests pass + the parity `assert_eq` held.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `chordal_mcs_max_clique_size`.
- Test-only: `chordal_treewidth_mcs_ab` A/B.

## Vein status

2nd win of the [[naive_maxscan_to_buckets_lever]] type (after is_chordal). Confirms the sweep value: chordal
kernels sharing the MCS pattern are all convertible. This one additionally carried a String→int conversion.
