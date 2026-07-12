# br-r37-c1-misbucket — maximum_independent_set: O(V·E) min-degree scan → O((V+E)·log V) min-degree buckets

Status: **SHIP.** 5.5407x on a 4000-node interval graph, byte-identical, STRICT gate. The decrementing
min-degree sibling of the MCS max-label buckets lever ([[naive_maxscan_to_buckets_lever]]); 3rd win of the type.

## The target

`maximum_independent_set(graph)` is a greedy MIS: repeatedly pick the remaining node of minimum effective
degree (ties by min node name), add it, and remove it + all its neighbours. The kernel (already integer-keyed,
`mismark`) was still **O(V·E)**: EVERY round it rescanned all remaining nodes AND recomputed each one's
effective degree via `neighbors_indices().filter(in_remaining).count()`.

## The lever

Min-degree weight buckets: `buckets[d]` (a `BTreeSet<&str>` of node NAMES) holds the remaining nodes whose
effective degree is d. Each round pops the smallest name in the lowest non-empty bucket. Effective degrees are
maintained **incrementally** — removing a node decrements each of its still-remaining neighbours by one (a
bucket move). `min_d` drops to the lowest freshly-created degree on a decrement, and is skipped up past
emptied buckets at the top of each round. **O((V+E)·log V)** total (each edge triggers O(1) bucket moves).

Distinct from the MCS lever in two ways: the weight DECREMENTS (min-degree, not max-label, and non-monotonic
`min_d`), and the tie-break is by NAME (lexicographic) so the buckets are `BTreeSet<&str>` (with a
`name_to_idx` map), not `BTreeSet<usize>`.

## Byte-identical argument

The old selection was `min (effective_degree, then node name)` — a total order (names unique) → a unique
minimum. The bucket reproduces it exactly: lowest non-empty bucket = min effective degree; `BTreeSet.first()`
= min name at that degree. Effective degrees are maintained to match the per-round recompute (seeded from
`neighbors_indices().len()`, so self-loops are counted identically; every node removal decrements exactly its
still-remaining neighbours, including double-decrements when a node neighbours two removed nodes). Verified:
`maximum_independent_set_mismark_ab` (production == the `HashSet<String>` baseline) passes AND the
`mis_bucket_ab` A/B asserts `old_fn(&g) == super::maximum_independent_set(&g)` (the previous `mismark` O(V·E)
scan vs the bucket) on a 4000-node interval graph; the `test_maximum_independent_set_{path,triangle,empty}`
suite passes.

## Median A/B (full function, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib mis_bucket_ab -- --ignored --nocapture`

5th-power-of-a-path interval graph (4000 nodes → large MIS → many peel rounds so the O(V·E) recompute
dominates). 61 rounds. Ratio = old-scan / bucket, **>1 = bucket faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BUCKET_vs_scan` | **5.5407x** | 61/61 | [4.4206, 7.4221] |
| `NULL_bucket_vs_bucket` | 1.0093x | 34/61 | [0.8747, 1.2010] |

Decisive: candidate p5 (4.42) is ~3.7x above the null p95 (1.20) — clears the STRICT gate; all 61 rounds won;
null centred on 1.0. Ratio GROWS with |V| (O(V·E)→O((V+E)logV)). Smaller than the chordal treewidth 176x
because that MCS was ALSO String-keyed (compounding); this one was already int-keyed, so it's the pure
scan→bucket delta.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `maximum_independent_set`.
- Test-only: `mis_bucket_ab` A/B.

## Vein status

3rd win of the buckets lever type — and the first DECREMENTING (min-degree) one, proving the pattern extends
beyond monotonic max-label MCS to min-degree peels (greedy MIS, degeneracy-style orderings). Next: other
greedy "pick min/max-degree remaining node, remove it + neighbours" loops (min-fill is harder — the key isn't
a simple degree). greedy_color smallest_last is this exact shape but peer-locked.
