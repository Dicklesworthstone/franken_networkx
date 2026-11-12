# second_order_centrality weighted path: O(n^4) -> O(n^3) via Sherman-Morrison-Woodbury

Bead lineage: `br-socwoodbury` (NO-CEILING addendum — algorithmic complexity-class
swing, not a micro-lever).

## Catastrophe

`second_order_centrality(G, weight=...)` with a weight (i.e. `weight=None`, a
custom weight key, or any graph carrying a `weight` edge attribute) hit the
Python fallback, which solved

    matrix[:, j] = solve(I - Q_j, ones)    for every column j = 0..n-1

where `Q_j` is the row-stochastic transition matrix with column `j` zeroed.
That is **n independent dense O(n^3) solves => O(n^4)** overall, and on this
host the per-iteration `transition.copy()` / `I - Q_j` allocation churn made the
effective scaling even worse than n^4. (The unweighted default already uses the
O(n^3) Rust fundamental-matrix kernel; only the weighted Python path was
affected.)

## Lever (one)

Every system differs from the common anchor `A = I - Q_0` by a **rank-2 update**:

    I - Q_j = A + p_j e_j^T - p_0 e_0^T,     p_k = transition[:, k].

`A = I - Q_0` is the absorbing fundamental matrix for sink node 0 and is
non-singular on a connected chain. By Sherman-Morrison-Woodbury, with
`a = A^{-1} ones` and `bp = A^{-1} transition` (one shared LU factorization,
solved as a single LAPACK call over the stacked RHS `[ones | transition]`):

    x_j = a - (A^{-1}U)(I_2 + V^T A^{-1} U)^{-1}(V^T a),
    U = [p_j, -p_0],  V = [e_j, e_0].

The 2x2 inner system has a closed form, so the whole correction **vectorizes
over j** (no Python loop, no per-column solve) -- O(n^2). Total cost: **O(n^3)**.
The centrality formula `sqrt(2*sum(col) - n(n+1))` is byte-unchanged. A
non-finite fast-path entry transparently falls back to the exact per-column
solves.

## Isomorphism / golden proof

`golden_sha256_isomorphism.py` digests results (rounded to 8 decimals, NaN
canonicalized) over a fixed 25-graph weighted corpus for the OLD exact n-solves,
the NEW Woodbury path, and networkx:

    golden_sha256_new_woodbury = ebb79e05aefe62c46e92f1e7cf66554f9449ca56e3aba8433ca9e119a3f02f41
    golden_sha256_old_nsolves  = ebb79e05aefe62c46e92f1e7cf66554f9449ca56e3aba8433ca9e119a3f02f41
    golden_sha256_networkx     = ebb79e05aefe62c46e92f1e7cf66554f9449ca56e3aba8433ca9e119a3f02f41
    ISOMORPHISM (old==new==nx): PASS
    raw max|new-old| = 8.5e-13

`proof_helper_vs_exact_and_nx.py`: across 60 weighted graphs the fast columns
match the exact per-column solves and networkx to ~1.5e-11 (matrix) / 2e-12
(centrality), 0 fallbacks. Live parity sweep: 80x2 weighted+custom-key graphs,
max err 1.65e-12, 0 mismatches; unweighted Rust path unchanged.

## Benchmark (same-process interleaved A/B, min of 5; weighted W-S graph)

    n      old O(n^4)   new O(n^3)   speedup
    60     0.0045 s     0.0030 s        1.5x
    100    0.446  s     0.017  s       26.6x
    140   16.69   s     0.077  s      217x

The new path is strictly faster at every size (no small-n regression after
dropping scipy LU for a single stacked-RHS `np.linalg.solve`), and the gap grows
with n -- a genuine complexity-class win. Score: Impact (>=27x at n>=100,
unbounded growth) x Confidence (0.97, exact golden match) / Effort (~1.5) >> 2.0.

## Files

- `python/franken_networkx/__init__.py`: `_second_order_fundamental_columns`
  helper + Woodbury fast path with exact-loop fallback in `second_order_centrality`.
- `tests/python/test_second_order_centrality_woodbury_parity.py`: parity tests.
