# adjacency_spectrum cycle_graph closed-form

Bead: `br-r37-c1-1auuy`

Duplicate bead `br-r37-c1-04z53.9127` was closed as superseded by this same pass.

Target: `fnx.adjacency_spectrum(fnx.cycle_graph(799))`

## Baseline

- Direct FNX median: `0.24175035004736856s`
- Direct FNX mean: `0.25411431660177186s`
- rch hyperfine three-call mean: `1.0181501219000002s`
- cProfile: 3 calls spent `0.653s` in `_fnx.symmetric_eigvals_rust`
- Golden sorted complex SHA q9: `cf5ef2be0a533f42b4f18ed1f12b376067df7953be7fbe4c6283002c8e0f7db3`

## Lever

Exact unweighted simple connected 2-regular `Graph` inputs now return the analytic cycle spectrum `2*cos(2*pi*k/n)` as sorted `complex128` values before dense adjacency construction and the generic eigensolver. Weighted-edge default semantics, non-cycle graphs, disconnected 2-regular graphs, directed graphs, subclasses, and multigraphs stay on existing routes.

## After

- Direct FNX median: `0.0006577749736607075s`
- Direct FNX mean: `0.0008636369952000677s`
- rch hyperfine three-call mean: `0.24856663590000005s`
- cProfile: 200 calls spend `0.397s` total, with no `_fnx.symmetric_eigvals_rust` frame
- Golden sorted complex SHA q9: `cf5ef2be0a533f42b4f18ed1f12b376067df7953be7fbe4c6283002c8e0f7db3`
- Max sorted delta vs NetworkX: `3.3084646133829665e-14`

## Proof

- dtype remains `complex128`
- sorted-value parity with NetworkX is preserved
- weighted cycle graphs with a default `weight` attribute fall back and match NetworkX
- non-cycle/disconnected/directed/empty routes are unchanged
- no ordering, tie-break, or RNG surface changed
- focused pytest: `12 passed`
- `py_compile`, `cargo fmt --check`, and `git diff --check` passed
- UBS Python scan was bounded with `timeout 60s`; it emitted no findings before timing out

Score: Impact `367.54` x Confidence `0.95` / Effort `1` = `349.16`; keep.
