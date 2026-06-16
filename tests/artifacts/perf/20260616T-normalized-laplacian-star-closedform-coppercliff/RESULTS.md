# normalized_laplacian_spectrum star_graph closed-form

Bead: `br-r37-c1-fb0et`

Target: `fnx.normalized_laplacian_spectrum(fnx.star_graph(798))`

## Baseline

- Direct FNX median: `5.778214147023391s`
- Direct FNX mean: `5.202489727200009s`
- rch hyperfine one-call mean: `0.9150088220466667s`
- cProfile: one call spent `5.887s` in `np.linalg.eigvalsh`
- Sorted-value parity max delta: `1.7763568394002505e-15`
- q9 sorted SHA: `ea3e4f82d18525734c453be1b09c9cdaa89e7737a5def2b118e83c51cce0dcd7`

## Lever

Exact unweighted simple star `Graph` inputs now return the analytic normalized Laplacian spectrum `[0, 1 repeated n-2, 2]` as sorted `float64` before matrix construction and eigensolver routing.

## After

- Direct FNX median: `0.0005613230168819427s`
- Direct FNX mean: `0.000652972818352282s`
- rch hyperfine one-call mean: `0.24653754716000004s`
- cProfile: 1000 calls spend `0.483s` total, with no normalized Laplacian matrix construction or eigensolver frame
- q9 sorted SHA: `ea3e4f82d18525734c453be1b09c9cdaa89e7737a5def2b118e83c51cce0dcd7`
- Max sorted delta vs NetworkX: `1.84297022087776e-14`

## Proof

- dtype remains `float64`
- sorted-value parity with NetworkX is preserved
- raw and zero-normalized q9 sorted SHA both match NetworkX exactly
- weighted star graphs with a default `weight` attribute are rejected by the fast guard and match NetworkX through the fallback path
- path/non-star graphs remain on the matrix route and match NetworkX
- empty and complete graph routes are unchanged
- no ordering, tie-break, or RNG surface changed
- focused pytest: `11 passed, 431 deselected`
- `py_compile`, `cargo fmt --check`, and `git diff --check` passed
- UBS Python scan was bounded with `timeout 180s`; it emitted no findings before timing out

Score: Impact `10294.21` x Confidence `0.95` / Effort `1` = `9779.50`; keep.
