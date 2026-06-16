# normalized_laplacian_spectrum complete_graph closed-form

Primary bead: `br-r37-c1-bwizc`

Duplicate bead `br-r37-c1-qj00p` was closed as superseded by the same proof bundle.

Target: `fnx.normalized_laplacian_spectrum(fnx.complete_graph(399))`

## Baseline

- Direct FNX median: `0.07446279999567196s`
- Direct FNX mean: `0.12365103919291869s`
- rch hyperfine three-call mean: `0.5138697156400001s`
- cProfile: 3 calls spent `5.500s` in `np.linalg.eigvalsh` after dense normalized Laplacian construction
- Sorted-value parity max delta: `1.1102230246251565e-15`
- q9 sorted SHA: `1b6d151ae1e0aaa7d8cfa14f0ab12b5d04c8e38ae1b02d1c5c0378c351013d59`

## Lever

Exact unweighted simple complete `Graph` inputs now return the analytic normalized Laplacian spectrum `[0, n/(n-1) repeated n-1]` as sorted `float64` before matrix construction and eigensolver routing.

## After

- Direct FNX median: `0.00035284896148368716s`
- Direct FNX mean: `0.0003096967935562134s`
- rch hyperfine three-call mean: `0.26389789252000007s`
- cProfile: 1000 calls spend `0.123s` total, with no normalized Laplacian matrix construction or eigensolver frame
- q9 sorted SHA: `1b6d151ae1e0aaa7d8cfa14f0ab12b5d04c8e38ae1b02d1c5c0378c351013d59`
- Max sorted delta vs NetworkX: `5.551115123125783e-15`

## Proof

- dtype remains `float64`
- sorted-value parity with NetworkX is preserved
- raw and zero-normalized q9 sorted SHA both match NetworkX exactly
- weighted complete graphs with a default `weight` attribute fall back and match NetworkX
- `K1` returns the NetworkX-compatible single zero eigenvalue
- non-complete/empty routes are unchanged
- no ordering, tie-break, or RNG surface changed
- focused pytest: `8 passed, 431 deselected`
- `py_compile`, `cargo fmt --check`, and `git diff --check` passed
- UBS Python scan was bounded with `timeout 180s`; it emitted no findings before timing out

Score: Impact `211.04` x Confidence `0.95` / Effort `1` = `200.49`; keep.
