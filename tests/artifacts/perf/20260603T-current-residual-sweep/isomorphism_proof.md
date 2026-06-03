# br-r37-c1-04z53.12 Isomorphism Proof

## Target

`normalized_laplacian_default` on deterministic BA(8000, 4, seed=12345) through
`franken_networkx.normalized_laplacian_matrix(G)`.

## Baseline

- Sweep artifact: `sparse_sweep_after_f67e7fc6b.jsonl`
- fnx mean: `0.040405606204876675s`
- fnx median: `0.040907763002905995s`
- NetworkX mean: `0.027710280200699343s`
- Golden digest: `aa810df87c3bc48287dcee99741e5a144bb8a4155d83a6d079520488b39769b8`
- Hyperfine process mean: `0.6283950155657143s`
- Hyperfine process median: `0.62153860328s`

## After

- Sample artifact: `after_normalized_laplacian_default_fnx.jsonl`
- fnx mean: `0.03663461566732925s`
- fnx median: `0.030849940005282406s`
- Golden digest: `aa810df87c3bc48287dcee99741e5a144bb8a4155d83a6d079520488b39769b8`
- Hyperfine process mean: `0.6093092731857144s`
- Hyperfine process median: `0.6083875549000001s`

## Invariants

- Ordering: node indices still come from the public `nodelist` order; missing,
  duplicate, and empty nodelist checks are preserved before the fast path.
- Tie-breaking: not applicable for sparse matrix export.
- Floating point: the fast path scales the `D - A` entries in the same operation
  order as the old `D_inv_sqrt @ ((D - A) @ D_inv_sqrt)` route. Self-loop-only
  zero diagonals are omitted to preserve COO byte output.
- RNG: no library RNG is used; the benchmark graph seed is fixed.
- Fallback: multigraphs, non-fnx graph objects, non-string weights, and present
  Python-visible weight attrs stay on the existing generic sparse route.

## Score

Impact 3 x Confidence 4 / Effort 2 = 6.0, so the change clears the keep bar.
