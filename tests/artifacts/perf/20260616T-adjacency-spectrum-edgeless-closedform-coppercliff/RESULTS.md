# adjacency_spectrum empty_graph closed-form

Bead: `br-r37-c1-04z53.9126`

Target: `fnx.adjacency_spectrum(fnx.empty_graph(799))`

## Baseline

- Direct FNX median: `0.026064679957926273s`
- Direct FNX mean: `0.0403975237859413s`
- rch hyperfine three-call mean: `0.43752514222s`
- cProfile: 3 calls spent `0.073s` in `_fnx.symmetric_eigvals_rust`
- Golden sorted complex SHA q9: `107b07b8aff44ae5451ac951731586e35fecfd52325d0a0e49389b64e8d93ff1`

## Lever

Exact nonempty edgeless simple `Graph` inputs now return a `complex128` zero vector before dense adjacency construction and the generic eigensolver. The guard preserves the empty-graph error path and leaves directed, multigraph, subclass, weighted-edge, and non-edgeless inputs on existing routes.

## After

- Direct FNX median: `0.0000034259865060448647s`
- Direct FNX mean: `0.000008479785174131394s`
- rch hyperfine three-call mean: `0.25061383598000003s`
- cProfile: 1000 calls spend `0.006s` total, with no `_fnx.symmetric_eigvals_rust` frame
- Golden sorted complex SHA q9: `107b07b8aff44ae5451ac951731586e35fecfd52325d0a0e49389b64e8d93ff1`
- Max sorted delta vs NetworkX: `0.0`

## Proof

- dtype remains `complex128`
- sorted-value parity with NetworkX is exact for the all-zero spectrum
- empty `Graph()` still raises like NetworkX
- no ordering, tie-break, floating-point, or RNG surface changed
- focused pytest: `10 passed`
- `py_compile`, `cargo fmt --check`, and `git diff --check` passed
- UBS Python scan was bounded with `timeout 60s`; it emitted no findings before timing out

Score: Impact `7607.94` x Confidence `0.95` / Effort `1` = `7227.54`; keep.
