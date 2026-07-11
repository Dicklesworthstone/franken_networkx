# br-r37-c1-zid1b straggler — MultiDiGraph single-source BFS on the CSR

Status: **SHIP.** 7.84x median, byte-identical. clippy clean.

## The target

`multidigraph_sssp_length_with_parents` — the native MultiDiGraph single-source BFS — was the lone
zid1b straggler still allocating a fresh `mdg.successors(node)` `Vec<&str>` per pop + a `HashSet<&str>`
visited (String hashing), while its siblings (`multidigraph_weak_components_indexed`,
`multidigraph_is_weakly_connected`, and the zid1b family, 6 fns 24-114x) already traverse the
revision-cached integer CSR (`mdg.csr()`).

## The lever

BFS over `mdg.csr().successors(node_idx)` (`&[u32]`) with a `Vec<bool>` mark array + integer queue,
mapping indices→names once at output — mirroring the sibling CSR functions exactly. No new
infrastructure: MultiDiGraph's `csr()` (revision-keyed `Arc<MultiDiCsr>`) already existed.

## Byte-identical argument

`build_csr` fills `succ_targets` from `successors[node].keys()` (the DISTINCT successors in
adjacency-row order) mapped to node indices — exactly the set and order `mdg.successors(node)` yields.
So `csr.successors(i) == [get_index_of(v) for v in mdg.successors(node_i)]`; BFS discovery order (hence
every `(node, length, parent)` tuple) is identical. Duplicate/parallel edges don't arise (keys are
distinct) and wouldn't change discovery order anyway (first-visit wins). Verified in-test:
`assert_eq!(csr_bfs(src), string_baseline(src))` for EVERY source.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-python --lib mdg_bfs_csr_ab -- --ignored --nocapture`

n=400 MultiDiGraph (ring + chords + parallels), ALL-PAIRS (BFS from every node, CSR reused). 61 rounds.
Ratio = base/cand, **>1 = CSR faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `CSR_vs_string` | **7.8407x** | 61/61 | [6.8028, 8.7176] |
| `NULL_csr_vs_csr` | 1.0078x | 35/61 | [0.8457, 1.1099] |

Clean & decisive: candidate p5 (6.80) ~6x above the NULL p95 (1.11); all 61 rounds won. The CSR is
revision-cached (built once, reused across sources), so this is the reuse win; a cold one-shot is
neutral (CSR build ≈ the old HashSet path's O(E) hashing, integer BFS strictly cheaper).

## Gates

- A/B `cargo test --release`: MDG_BFS_AB present (not stale); parity `assert_eq!` green for every source.
- clippy `-D warnings`: clean.
- Directed twin of the Slice-2 MultiGraph BFS win (11.69x); same byte-identity + measurement discipline.

## Files

- Production: `crates/fnx-python/src/algorithms.rs` — `multidigraph_sssp_length_with_parents`.
- Test-only: `..._orig_string` baseline + `mdg_bfs_csr_ab` A/B.
