# bfs_tree indexed result construction isomorphism proof

Bead: `br-r37-c1-04z53.38`

## Candidate behavior

The candidate preserved the existing traversal source:

- Same graph input: BA(3000, 4, seed=42) replayed into both FNX and NetworkX oracle graphs.
- Same BFS neighbor order: the edge stream still came from the existing indexed BFS traversal.
- Same tree edge order: output SHA stayed unchanged at `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64`.
- No floating-point or RNG path changed.
- Node and edge attrs for the returned BFS tree remained empty dicts.

## Rejection proof

The candidate was behavior-isomorphic but did not prove enough performance gain:

- Direct repeat-50 mean: `0.007129831201164052s -> 0.006317437958787195s`
- Hyperfine mean: `0.43992501238666665s -> 0.43277942618s`
- Hyperfine confirm mean: `0.43308385356000006s`

After rejection:

- Candidate source was manually removed from `crates/fnx-algorithms/src/lib.rs` and `crates/fnx-python/src/algorithms.rs`.
- `rg bfs_edges_indices crates/fnx-algorithms/src/lib.rs crates/fnx-python/src/algorithms.rs` returned no matches.
- `git diff -- crates/fnx-algorithms/src/lib.rs` was empty.
- The release extension was rebuilt from restored source.
- Restored sample SHA returned to `1080bb4f9f5cb05745326b002917767f0f0693de81f277c7cb6df03e49d14b76`.

Verdict: no algorithm or binding source from this candidate is kept.

