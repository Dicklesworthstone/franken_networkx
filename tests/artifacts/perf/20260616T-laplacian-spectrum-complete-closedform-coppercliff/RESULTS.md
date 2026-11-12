# laplacian_spectrum complete_graph closed-form

Bead: `br-r37-c1-fro10`

Target: `fnx.laplacian_spectrum(fnx.complete_graph(399))`

## Baseline

- Direct FNX median: `0.04694215499330312s`
- Direct FNX mean: `0.06137681419495493s`
- rch hyperfine three-call mean: `0.5191769095s`
- cProfile: 3 calls spent `0.181s` in Laplacian matrix construction and `0.092s` in `_fnx.symmetric_eigvals_rust`
- Sorted-value parity max delta: `1.3642420526593613e-12`

## Lever

Exact unweighted simple complete `Graph` inputs now return the analytic Laplacian spectrum `[0, n repeated n-1]` as sorted `float64` before matrix construction and eigensolver routing.

## After

- Direct FNX median: `0.00012341298861429095s`
- Direct FNX mean: `0.0001911737839691341s`
- rch hyperfine three-call mean: `0.26901205134s`
- cProfile: 1000 calls spend `0.136s` total, with no Laplacian matrix construction or eigensolver frame
- Zero-normalized contract SHA q9: `69ab4bfa8252b807f8e82bebeb78c23f6e73e297b687cd0c22c9d1d367201af2`
- Max sorted delta vs NetworkX: `1.6484591469634324e-12`

## Proof

- dtype remains `float64`
- sorted-value parity with NetworkX is preserved
- raw q9 SHA differs because the prior eigensolver emitted tiny signed zero artifacts; the zero-normalized q9 SHA matches exactly
- weighted complete graphs with a default `weight` attribute fall back and match NetworkX
- non-complete/empty routes are unchanged
- no ordering, tie-break, or RNG surface changed
- focused pytest: `16 passed`
- `py_compile`, `cargo fmt --check`, and `git diff --check` passed
- UBS Python scan was bounded with `timeout 60s`; it emitted no findings before timing out

Score: Impact `380.36` x Confidence `0.95` / Effort `1` = `361.34`; keep.
