# br-r37-c1-thp6w Slice 2 — MultiGraph single-source BFS on the integer-adjacency memo

Status: **SHIP.** 11.69x median on repeated single-source (memo reused), byte-identical.

## The target

`multigraph_sssp_length_with_parents` (tagged `br-r37-c1-fyxma3 cc`) is the native single-source
BFS over a MultiGraph's adjacency — the ONLY native MultiGraph neighbor-traversal consumer (all
other MultiGraph algos project to a simple Graph, already integer). It allocated a fresh
`mg.neighbors(node)` `Vec<&str>` per pop and used a `HashSet<&str>` visited (String-content
hashing per neighbor).

## The lever (first real consumer of the Slice 1 memo)

Traverse `with_int_adjacency(|adj| ...)` (the revision-keyed integer-adjacency memo added in Slice 1)
with a `Vec<bool>` mark array + integer queue, mapping indices→names once at output. `adj[i]` lists
node `i`'s distinct neighbors in the SAME adjacency-row order `mg.neighbors` yields, so BFS discovery
order — hence every `(node, length, parent)` tuple — is byte-identical.

## Byte-identical argument

Same source resolution (`get_node_index` vs the linear-scan `find` — both detect presence
identically), same neighbor order, same first-visit semantics (`!visited[v]` == `HashSet::insert`
returning true), same discovery/queue order → identical output after index→name mapping. Verified
in-test: `assert_eq!(integer_bfs(src) , string_baseline(src))` for EVERY source.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-python --lib mg_bfs_intadj_ab -- --ignored --nocapture`

n=400 connected MultiGraph (ring + chords + parallels), ALL-PAIRS (BFS from every node → V
single-source calls reusing one memo). 61 rounds. Ratio = base/cand, **>1 = integer faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INTADJ_vs_string` | **11.6896x** | 61/61 | [9.1766, 13.8483] |
| `NULL_intadj_vs_intadj` | 0.9877x | 19/61 | [0.9015, 1.0782] |

Clean & decisive: candidate p5 (9.18) is ~8.5x above the NULL p95 (1.08); all 61 rounds won.

## What the 11.69x means (honest scope)

This measures the memo-REUSE scenario: the revision-keyed memo is built once (first source) and
reused across all subsequent single-source calls on the unmutated graph. The production caller
`single_source_shortest_path_length` is single-source, so the win lands when the SAME MultiGraph is
queried from multiple sources (calls 2+ get near-free BFS). A COLD one-shot call is neutral by
construction — the memo build does the same O(E) String hashing the old `HashSet` path did, and the
integer BFS (`Vec<bool>` + integer queue) is strictly cheaper than the `HashSet<&str>` + per-pop
`Vec<&str>` path — so there is no one-shot regression.

## Gates

- A/B `cargo test --release -p fnx-python --lib`: MG_BFS_AB present (not stale); parity `assert_eq!`
  green for every source.
- Full fnx-python suite: green (byte-identity of the production change — see validation.log).
- clippy `-D warnings`: clean.
- Order-mutator audit (Slice 1 prerequisite) completed before adding this production reader: every
  content mutation bumps `revision`; `apply_row_orders` (the only order-only mutator) clears the memo.

## Files

- Production: `crates/fnx-python/src/algorithms.rs` — `multigraph_sssp_length_with_parents`.
- Test-only: `..._orig_string` baseline + `mg_bfs_intadj_ab` A/B.
- Depends on Slice 1 `MultiGraph::with_int_adjacency` (fnx-classes).
