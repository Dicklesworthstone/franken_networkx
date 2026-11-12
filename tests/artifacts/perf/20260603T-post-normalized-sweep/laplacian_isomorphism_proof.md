# br-r37-c1-04z53.13 Isomorphism Proof

## Target

`laplacian_default` on deterministic BA(8000, 4, seed=12345) through
`franken_networkx.laplacian_matrix(G)`.

## Baseline

- Sweep artifact: `sparse_sweep_after_63c6d202c.jsonl`
- fnx mean: `0.0323103444010485s`
- fnx median: `0.03348515399557073s`
- NetworkX mean: `0.023273729399079457s`
- Golden digest: `bca361dbcc78a18bc70f73d2dec30cc09d245e30218842df631d2bd79c1a2306`
- Hyperfine process mean: `0.6834997589657145s`
- Hyperfine process median: `0.6967977756800001s`

## After

- Sample artifact: `after_laplacian_default_fnx.jsonl`
- fnx mean: `0.03418378133452885s`
- fnx median: `0.028133939995313995s`
- Golden digest: `bca361dbcc78a18bc70f73d2dec30cc09d245e30218842df631d2bd79c1a2306`
- Hyperfine process mean: `0.60231325912s`
- Hyperfine process median: `0.62198274612s`

The after sample mean includes one cold outlier at `0.10553293600969482s`; the
hot-call median and hyperfine process both improved.

## Invariants

- Ordering: node indices still come from the public `nodelist` order; missing,
  duplicate, and empty nodelist checks are preserved before the fast path.
- Tie-breaking: not applicable for sparse matrix export.
- Integer dtype: unit/default-absent data stays `int64`, matching the previous
  unweighted adjacency and `D - A` sparse route.
- Self-loops: diagonal entries are `degree - self_loop_count`; self-loop-only
  zero diagonals are omitted to preserve sparse structure.
- RNG: no library RNG is used; the benchmark graph seed is fixed.
- Fallback: multigraphs, non-fnx graph objects, non-string weights, and present
  Python-visible weight attrs stay on the existing generic sparse route.

## Score

Impact 3 x Confidence 4 / Effort 2 = 6.0, so the change clears the keep bar.
