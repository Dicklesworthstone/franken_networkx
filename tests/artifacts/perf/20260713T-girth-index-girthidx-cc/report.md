# br-r37-c1-girthidx — girth: per-source String-keyed BFS → integer-index stamped BFS

Status: **SHIP.** 32.7144x, byte-identical, STRICT gate by a mile. 2nd multi-round String→int win after
voterank (br-r37-c1-voterankidx) — same magnitude.

## The target

`girth(graph)` finds the shortest cycle by running a BFS from **every** node (looking for the shortest
back-edge). Each BFS kept `dist: HashMap<&str, usize>` and `parent: HashMap<&str, &str>`, so it paid a String
hash on every `dist`/`parent` probe across O(|V|·(|V|+|E|)) BFS steps.

## The lever

Walk `neighbors_indices` over node INDICES with reusable `dist: Vec<usize>` / `parent: Vec<usize>`, using a
per-source **epoch stamp** (`seen: Vec<u32>`) to mark "visited this BFS" — no realloc and no O(n) clear between
the |V| sources. Zero String hashing in the traversal.

## Byte-identical argument

`min_girth` is an order-independent **minimum** over the same set of BFS-discovered back-edge cycles: the same
nodes are explored (BFS over the same adjacency), the same cycle lengths `d_v + d_w + 1` are computed, and the
early-exit `d_v*2+1 >= min_girth` (monotone `min_girth`) and the parent-edge skip are unchanged. The source has
no parent (`parent[source] = usize::MAX`, which never equals a real neighbour index), matching the old
`parent.get(source) = None`. Verified: the A/B asserts `old_fn(&g) == super::girth(&g)` (inline String-keyed
BFS vs the shipped index BFS) on a 1200-node ring; all 5 `test_girth_{triangle,square,tree,empty,multiple_cycles}`
suite tests pass.

## Median A/B (full function, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib girth_idx_ab -- --ignored --nocapture`

Ring C₁₂₀₀ (girth 1200) → BFS from every node explores the whole ring (deep BFS), maximising the String-hash
cost. 61 rounds. Ratio = String / index, **>1 = index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INDEX_vs_string` | **32.7144x** | 61/61 | [29.5797, 37.7600] |
| `NULL_index_vs_index` | 0.9996x | 30/61 | [0.8937, 1.0612] |

Decisive beyond question: candidate p5 (29.58) is ~28x above the null p95 (1.06); all 61 rounds won; null
centred on 1.0.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `girth`.
- Test-only: `girth_idx_ab` A/B.

## Vein status

2nd multi-round String→int win (voterank 32.9x, girth 32.7x). Confirms the reusable lesson: **String-keyed
per-source/per-round BFS/DFS/accumulate loops that run O(|V|) traversals are huge (~30x) residuals** even where
single-pass String→int is mined out. Grep `HashMap<&str,_>`/`HashSet<&str>` inside a `for &source in &nodes`
(or multi-round `loop`/`while`). Convert to `neighbors_indices` + epoch-stamped Vec state. See
[[naive_maxscan_to_buckets_lever]] (voterank note) and [[cc_string_to_int_vein_mined_out]].
