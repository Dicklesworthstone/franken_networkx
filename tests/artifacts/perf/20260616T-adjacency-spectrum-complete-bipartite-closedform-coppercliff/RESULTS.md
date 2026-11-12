# adjacency_spectrum complete_bipartite_graph closed-form

Bead: `br-r37-c1-iny15`

Target: `fnx.adjacency_spectrum(fnx.complete_bipartite_graph(399, 400))`

## Baseline

- Direct FNX median: `8.64891768002417s`
- Direct FNX mean: `9.142650098807644s`
- rch hyperfine one-call mean: `3.0745391284199997s`
- cProfile: 1 call spent `0.261s` in `_fnx.symmetric_eigvals_rust`, then `7.586s` in SciPy `eig` fallback
- Raw sorted complex SHA q9: `8dff67db0d97aa363ad6e0667b0daf99aa7d73f621a7d3b1aaa094393f95cdd6`

## Lever

Exact unweighted simple connected complete-bipartite `Graph` inputs now return the analytic spectrum `{-sqrt(p*q), 0..., +sqrt(p*q)}` as sorted `complex128` values before dense adjacency construction and eigensolver fallback. The route runs after the star helper so exact star raw-order behavior remains unchanged.

## After

- Direct FNX median: `0.11051670898450539s`
- Direct FNX mean: `0.14614639041246846s`
- rch hyperfine one-call mean: `0.6569910167333334s`
- cProfile: 5 calls spend `0.981s` total, with no `_fnx.symmetric_eigvals_rust` or SciPy `eig` frame
- Zero-normalized contract SHA q9: `2c93498c7f6becfffe981afac5bea868ea1a2826845681456380060e21e36849`
- Max sorted delta vs NetworkX: `1.1937117960769683e-12`

## Proof

- dtype remains `complex128`
- sorted-value parity with NetworkX is preserved
- raw q9 SHA differs because the prior SciPy fallback emitted tiny signed nullspace residuals that round to signed zero; the zero-normalized q9 SHA matches exactly
- weighted complete-bipartite graphs with a default `weight` attribute fall back and match NetworkX
- non-complete-bipartite/disconnected/directed/empty routes are unchanged
- star raw-order route stays ahead of this route
- no ordering, tie-break, or RNG surface changed
- focused pytest: `14 passed`
- `py_compile`, `cargo fmt --check`, and `git diff --check` passed
- UBS Python scan was bounded with `timeout 180s`; it emitted no findings before timing out

Score: Impact `78.26` x Confidence `0.95` / Effort `1` = `74.35`; keep.
