# perf(gnp_random_graph directed): native generator

br-r37-c1-ovczr (gnp_directed part)

## Problem
`gnp_random_graph(..., directed=True)` ran a PURE-PYTHON `O(V^2)` loop in the
wrapper: `for u, v in itertools.permutations(range(n), 2): if rng.random() < p:
graph.add_edge(u, v)` — `V*(V-1)` Python iterations + a per-kept-edge PyO3
`add_edge` crossing. **2.0–3.6× slower than nx** (n=1500 p=0.3: 2.30 s vs nx
0.63 s). The undirected case already had a native generator; the directed case
did not.

## Lever (one)
Add a native `gnp_random_digraph` (fnx-generators) that reproduces nx's exact
output: it walks `permutations(range(n), 2)` order (source-major, every target
`!= source`), drawing one `PythonRandom::random()` per ordered pair — the SAME
MT19937/gen_res53 generator the proven undirected native path uses — and adds
the edge when the draw is `< p`. Wire a `gnp_random_digraph` binding (→
`report_to_pydigraph`) and route the wrapper's directed case to it for
`create_using is None`, strict `0 < p < 1`, non-negative int seed. (`p<=0`/`p>=1`
and negative/None/non-int seeds keep the nx-matching Python path — the native
`_native_random_seed` hashing diverges from `random.Random` on negatives, a
pre-existing undirected behavior we do NOT extend.)

Touched: `crates/fnx-generators/src/lib.rs` (+`gnp_random_digraph`),
`crates/fnx-python/src/generators.rs` (+binding/register),
`python/franken_networkx/__init__.py` (import + directed route).

## Proof (nx-exact)
`harness_proof.py`: 79 cases — n∈{30,60,100} × p∈{0.05,0.1,0.3,0.5} × 6 seeds,
plus edge cases (n=0/1/2, p=0.0001/0.999) and negative seeds (Python fallback).
**0 mismatches vs nx** on the full ORDERED edge list (`G.edges()`), not just the
set. Golden sha256 (== nx):
`5b0e61d94e9440908981042adb6044abc2c1926c5b9d2830919ab3c072bd3423`
pytest -k "gnp/erdos/random_graph": **1287 passed**.

## Timing (warm interleaved min-of-4, backend disabled, gnp directed)
| n    | p    | baseline fnx | nx       | baseline ratio | new fnx   | new ratio | self-speedup |
|------|------|-------------:|---------:|---------------:|----------:|----------:|-------------:|
| 1000 | 0.1  |   321.6 ms   | 134.4 ms |     2.42×      |  184.7 ms |   1.37×   |    1.74×     |
| 1500 | 0.1  |   771.4 ms   | 302.7 ms |     2.55×      |  432.0 ms |   1.43×   |    1.79×     |
| 1500 | 0.3  |  2295.9 ms   | 617.5 ms |     3.64×      | 1330.3 ms |   2.15×   |    1.73×     |
| 2000 | 0.05 |   862.9 ms   | 400.7 ms |     1.99×      |  407.3 ms | **1.02×** |    2.12×     |

1.73–2.12× self-speedup; sparse (p=0.05) reaches nx parity. HONEST RESIDUAL: the
dense cases stay 1.4–2.15× slower — the O(V^2) draw loop is now native, but
building the inner DiGraph (succ/pred index + edges IndexMap for up to ~675k
edges) is the bulk-construction substrate (br-r37-c1-71x9k, still deferred).

## Score
Impact: high (eliminates a pure-Python O(V^2) loop on a core generator;
1.73–2.12× self-speedup, parity at sparse density, ~1 s saved at n=1500 p=0.3).
Confidence: high (byte-identical ordered golden sha incl. edge-case + negative
seeds, 0/79, 1287 tests). Effort: moderate (3-layer native generator, reusing
PythonRandom). Score >> 2.0.
