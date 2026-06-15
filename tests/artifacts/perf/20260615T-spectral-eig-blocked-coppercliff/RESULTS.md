# br-r37-c1-04z53.9111 Lower-Triangle Matvec Rejection

## Target

First deeper pass after the safe-Rust `laplacian_spectrum` route: test whether
local Householder loop reshapes can reduce tridiagonalization cost before
moving to a full blocked-panel `dsytrd` implementation.

## Baseline

- Harness: `eig_baseline_harness.py`.
- Case: weighted Laplacian dense matrix, raw `_fnx.symmetric_eigvals_rust`.
- Baseline native `n=100`: mean `0.0008049273705442569s`, median
  `0.0008026160998269915s` per loop.
- Baseline native `n=200`: mean `0.0054192583958086165s`, median
  `0.005613997799810022s` per loop.
- NumPy comparator baseline: `n=100` mean `0.0002750746423511633s`;
  `n=200` mean `0.0012278083994585489s`.

## Lever 1

Tried a single lower-triangle pass for the symmetric matrix-vector product
inside Householder reduction, accumulating both `e[row]` and `e[col]` while
walking the stored lower triangle.

## Proof

- Golden after: max abs delta `1.7763568394002505e-13`, max rel delta
  `2.2316783837587147e-14`.
- Quantized native/Numpy SHA match:
  `87d7992502970de75d14e5c24ae33a702c010a18660e31e9f6eb0c299c994f64`.
- Behavior was unchanged, but runtime regressed.

## After

- After native `n=100`: mean `0.0008916267119015434s`, median
  `0.0008914633945096284s` per loop.
- After native `n=200`: mean `0.006212104514374264s`, median
  `0.0059537468012422325s` per loop.
- Slowdown: `0.90x` at `n=100` and `0.87x` at `n=200` by mean.

## Lever 2

Tried a Rayon-parallel rank-2 trailing update for active panels of size >=128,
copying the reflector and adjusted update vector into scratch slices before
parallel row updates.

## Lever 2 Proof

- Golden after: max abs delta `1.7763568394002505e-13`, max rel delta
  `2.2316783837587147e-14`.
- Quantized native/Numpy SHA match:
  `87d7992502970de75d14e5c24ae33a702c010a18660e31e9f6eb0c299c994f64`.
- Behavior was unchanged, but runtime regressed.

## Lever 2 After

- After native `n=100`: mean `0.0008465572426627789s`, median
  `0.0007826150045730174s` per loop.
- After native `n=200`: mean `0.01743651734265898s`, median
  `0.01613893558969721s` per loop.
- Slowdown: `0.95x` at `n=100` and `0.31x` at `n=200` by mean.

## Decision

Rejected both local loop reshapes. Scores are below the keep bar. Source changes
were removed; evidence is retained so the next 9111 pass should skip local
dot/matvec and thread-per-row reshuffles and attack the real blocked-panel
Householder primitive: compact reflector panels, form `W`, and apply a
cache-blocked symmetric rank-2k trailing update.
