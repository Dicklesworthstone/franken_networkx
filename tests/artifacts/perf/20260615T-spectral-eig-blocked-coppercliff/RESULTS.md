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

## Lever 3

Kept the reflector row in a scratch slice and reused cached row offsets during
the Householder symmetric matrix-vector and rank-2 update sweeps. This keeps the
same algorithm and ordering, but removes repeated `i * n + k` addressing from
the inner loops and lets the compiler see a compact immutable reflector slice.

## Lever 3 Proof

- Golden after: max abs delta `1.7763568394002505e-13`, max rel delta
  `2.2316783837587147e-14`.
- Quantized native/Numpy SHA match:
  `87d7992502970de75d14e5c24ae33a702c010a18660e31e9f6eb0c299c994f64`.
- Native solver still returns ascending eigenvalues; no RNG or tie-break surface.

## Lever 3 After

- After native `n=100`: mean `0.0007917463147480572s`, median
  `0.0007757890969514846s` per loop.
- After native `n=200`: mean `0.0046519630239345135s`, median
  `0.004501029395032674s` per loop.
- Speedup: `1.02x` at `n=100` and `1.16x` at `n=200` by mean.

## Packed-Threshold Variant

Also measured a thresholded variant that only copied the reflector for
`active_len >= 128`. It preserved the same SHA but was weaker than the
unconditional scratch path: `n=100` mean `0.000849185571340578s`, `n=200` mean
`0.004877143261754619s`. It was not kept.

A gated packed follow-up also preserved the same SHA but was not selected:
`n=100` mean `0.0008939508290495723s`, `n=200` mean
`0.004679433113363172s`; unconditional scratch remains the kept source.

## Decision

Kept Lever 3 only. The lower-triangle matvec and thread-per-row rank-2 update
were rejected and removed, and the packed-threshold variant was not kept. The
reflector scratch/indexing lever is a low-effort `1.16x` n=200 improvement with
unchanged golden output. It does not complete 9111: the next pass still needs
the real blocked-panel Householder primitive with compact reflector panels, `W`
formation, and a cache-blocked symmetric rank-2k trailing update.
