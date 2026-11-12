# br-r37-c1-9brc9 rejection report

## Target

`random_regular_graph(d=20, n=400, seed=123)` default `Graph` path.

Baseline profile on `origin/main` showed the wrapper already produces a real
CPython edge set via `_rust_random_regular_edges_pyset`, then pays conversion
tax in `Graph.add_edges_from`:

- total: `0.449s` / 100 calls
- `random_regular_edges_pyset`: `0.103s`
- `Graph.add_edges_from`: `0.296s`
- `_try_add_edges_from_batch`: `0.215s`
- Python list append while materializing the set: `400111` calls, `0.035s`

## Lever tried

Accept exact `PySet` in the existing attr-free `PyGraph` plain-edge batch path
and let the Python wrapper call `_try_add_edges_from_batch` directly for exact
sets. This preserved CPython set iteration order by iterating the same set once,
without sorting or using a Rust `HashSet`.

## Proof

Baseline, candidate, and restored-source proof SHA:

`2b68b0530c53af35bef3c5adb0cb7dc3e9bbdb9ef90553bf15186e667d332784`

The proof covers:

- seeded `random_regular_graph` node/edge/adjacency order against NetworkX
- direct `PySet` vs `list(PySet)` edge insertion order
- hash-equal mixed display fallback
- bad-arity set fallback and partial-error surface
- global `add_edges_from(..., weight=7)` attr guard

Ordering, tie-breaking, and RNG behavior were unchanged. Floating point is N/A.

## Performance

Whole-process hyperfine, 25 builds/process:

- baseline: `380.634ms +/- 22.0ms`
- candidate: `378.418ms +/- 30.1ms`
- verdict: flat/noise, not a confirmed win

Direct harness:

- `rr_20_400_seed123`: median `4.892ms -> 3.758ms` (`1.30x`)
- smaller fixed-seed cases regressed or stayed flat

Same-binary old-path emulation (`add_edges_from(list(edges))`) vs candidate
direct set path, 100 builds/process:

- old emulation: `660.4ms +/- 38.5ms`
- direct set: `627.3ms +/- 23.2ms`
- speedup: `1.05x +/- 0.07`

Candidate profile:

- total: `0.365s` / 100 calls
- `_try_add_edges_from_batch`: still `0.215s`
- list append calls removed, but the collector remains dominant

## Verdict

Rejected. The lever is proof-clean but does not clear the Score >= 2.0 keep
gate and does not produce a robust RCH/hyperfine win.

## Next route

Do not retry PySet/list materialization shortcuts. The remaining target is a
dedicated exact-int pair-set builder that consumes the CPython set in yielded
order but bypasses the generic plain-edge collector's per-edge display-conflict,
canonicalization, and tuple handling overhead. Guard it to exact `(int, int)`
edge tuples on exact `Graph` with no attrs, and prove against the same artifact
suite before benchmarking.
