# resistance_distance single-pair: dense O(n^3) pinv -> O(nnz) grounded sparse solve

Bead: `br-r37-c1-resistance-distance-single-pair-pinv-bdr8q` (filed prior session).

## Catastrophe

`resistance_distance(G, nodeA, nodeB)` with both endpoints — the common
single-scalar call — built the FULL dense Laplacian pseudo-inverse
`np.linalg.pinv(L, hermitian=True)` (O(n^3)) and then read four entries
`L^+[i,i] + L^+[j,j] - L^+[i,j] - L^+[j,i]`.

## Lever (one)

The single effective resistance is `r(i,j) = (e_i - e_j)^T L^+ (e_i - e_j)`.
Because `(e_i - e_j) ⟂ ones`, this equals `(e_i - e_j)^T x` for ANY solution of
`L x = (e_i - e_j)`. Ground node 0 (drop its row/col): the reduced Laplacian
`L_red` is sparse SPD for a connected graph, and

    r(i,j) = (e_i - e_j)_red^T L_red^{-1} (e_i - e_j)_red = vr · spsolve(L_red, vr).

One sparse SPD solve — **O(nnz)** — replaces the dense **O(n^3)** pinv. The dict
(`nodeA`-only / `nodeB`-only) and all-pairs shapes need `diag(L^+)`, so they keep
the dense pinv. A non-finite sparse result falls back to the dense path.

## Isomorphism / golden proof

`golden_sha256_isomorphism.py` over a 20-graph corpus (weighted + unweighted,
8 random pairs each), values rounded to 8 dp:

    golden_sha256_sparse_solve = 7ff4bac57284d6559974c041dc1fd533aec8b41df7fc3530672b46a29e797626
    golden_sha256_dense_pinv   = 7ff4bac57284d6559974c041dc1fd533aec8b41df7fc3530672b46a29e797626
    golden_sha256_networkx     = 7ff4bac57284d6559974c041dc1fd533aec8b41df7fc3530672b46a29e797626
    ISOMORPHISM (sparse==dense==nx): PASS

`proof_grounded_vs_pinv.py`: grounded solve vs pinv formula, max err 3.3e-15
across 60 weighted/unweighted graphs. Live parity (all 4 return shapes, both
`invert_weight`): max err 1.24e-14, 0 mismatches.

## Benchmark (same-process A/B: sparse path vs forced dense pinv; W-S graph)

    n      dense_pinv    sparse_solve   speedup
    300     2.8135 s      0.0022 s       1265x
    800     9.0735 s      0.0150 s        604x
    1500   18.3759 s      0.0816 s        225x

The sparse solve scales with nnz (2 -> 82 ms) while the dense pinv is O(n^3)
(2.8 -> 18 s). Score: Impact (>=225x, growing) x Confidence (0.98, exact golden) /
Effort (~1.2) >> 2.0.

## Note on parallel work

A credit-limited cod pane independently proved the same lever
(`tests/artifacts/perf/20260604T-resistance-distance-single-pair-sparse/`,
golden_after fnx==dense_exact==nx) but stalled before committing; this commit
lands the proven win. Artifacts kept in a separate `-cc` dir; the peer's dir is
untouched.

## Files

- `python/franken_networkx/__init__.py`: `_resistance_single_pair_sparse` helper
  + single-pair fast path in `resistance_distance` (dense pinv fallback retained).
- `tests/python/test_resistance_distance_single_pair_sparse_parity.py`.
