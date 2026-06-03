# ego_graph EdgeDataView Materialize Bypass Proof

Bead: `br-r37-c1-04z53.25`

Target: `ego_graph(Graph, 0, radius=2)` on `barabasi_albert_graph(3000, 4, seed=42)`.

## Profile-Backed Target

Baseline profile showed 7 `ego_graph` calls taking `0.511s` cumulative. The simple-graph edge copy loop spent `0.119s` in `_FailFastEdgeIterator.__next__`, `0.083s` in repeated `len`, and `0.078s` materializing `EdgeDataView`.

## Lever Evaluated

In the internal simple-Graph copy path, bypass the public fail-fast iterator when `G.edges(data=True)` returns the module-local `EdgeDataView` and iterate `EdgeDataView._materialize()` directly.

## Behavior Isomorphism

Ordering: the candidate consumed the same `_materialize()` list that the public iterator wraps, so edge order and undirected orientation were unchanged.

Tie-breaking: the node set is computed before edge copying, and the candidate did not alter neighborhood traversal, shortest-path distance checks, or membership filtering.

Floating point: this unweighted radius case performs no floating-point accumulation in the changed path.

RNG: the library path uses no RNG. The benchmark graph seed is fixed at `42`.

Golden output: baseline, candidate, candidate repeat-21, and restored runs all emitted digest `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`.

## Benchmark Result

Baseline fnx repeat-7 mean: `0.04495093485664776s`.

Candidate fnx repeat-7 mean: `0.052583811141500646s`.

Candidate fnx repeat-21 mean: `0.05161768471242838s`.

Restored fnx repeat-7 mean: `0.04541956599652102s`.

Hyperfine baseline: `556.7 ms +/- 32.5 ms`.

Hyperfine candidate: `531.7 ms +/- 13.5 ms`; candidate repeat-20 hyperfine: `552.8 ms +/- 102.2 ms`.

The focused profile improved (`ego_graph` cumulative `0.511s` to `0.350s`), but the direct timing regressed and the process-level hyperfine evidence did not prove a stable win.

Score: Impact 1 x Confidence 3 / Effort 3 = 1.0.

Verdict: rejected; no source code kept.
