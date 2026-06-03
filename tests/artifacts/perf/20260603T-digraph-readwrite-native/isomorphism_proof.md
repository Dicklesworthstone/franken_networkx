# Isomorphism Proof: Directed Native `to_dict_of_*`

- Bead: `br-r37-c1-nocb2`
- Commit lever: exact simple `DiGraph` now uses the same native `to_dict_of_dicts_undirected` / `to_dict_of_lists_undirected` helpers as exact simple `Graph`, with directed arms.

## Profile-Backed Target

Baseline cProfile, rch:

- `to_dict_of_dicts`: `1.166s` cumulative over 20 conversions in the Python `AdjacencyView` path.
- `to_dict_of_lists`: `0.324s` cumulative over 20 conversions in wrapper/neighbor membership work.

After cProfile, rch:

- `to_dict_of_dicts`: `0.063s` cumulative over 20 conversions in the native binding.
- `to_dict_of_lists`: `0.012s` cumulative over 20 conversions in the native binding.

## Benchmark Delta

Direct repeat-11 conversion mean, rch:

- `dicts`: `0.03819380481780337s -> 0.003956229269864376s`
- `lists`: `0.0047900736443063415s -> 0.0005332469088237056s`

Isolated hyperfine loop, rch, 100 conversions per run:

- `dicts`: `4.55867636722s +/- 0.13639872296538103s -> 0.55450878054s +/- 0.017435464611009165s`
- `lists`: `0.9039141404200001s +/- 0.03135321889153903s -> 0.45295812614s +/- 0.02359133275217979s`

The initial one-conversion hyperfine artifact is also preserved; it is intentionally not the scoring artifact because import and graph construction dominate a single conversion.

## Behavior Isomorphism

- Output key order is unchanged: the native path iterates `nodes_ordered()`, matching the Python fallback's `list(G.nodes())` / `for n in G`.
- Directed neighbor order is unchanged: the native path iterates `successors_iter(u)`, matching `DiGraph.neighbors(u)` / `G[u].items()` for NetworkX-observable successor order.
- Edge orientation is unchanged: the directed arm uses ordered `(u, v)` edge keys and never canonicalizes `(v, u)`.
- Edge-data object identity is unchanged for the default `edge_data=None` path: `to_dict_of_dicts(G)[u][v] is G[u][v]` remains true in the golden harness.
- Exact-type gates preserve fallback semantics for subclasses, filtered views, multigraphs, `nodelist`, and `edge_data` override paths.
- Tie-breaking is not otherwise involved; traversal order remains insertion/successor order.
- Floating-point arithmetic is not touched.
- RNG is not touched; the benchmark graph seed remains `17`.

Golden SHA, rch:

- Baseline: `6462260fb3887b9795744204965171236693f42518c4bef876669fb0a4f8625a`
- After: `6462260fb3887b9795744204965171236693f42518c4bef876669fb0a4f8625a`

## Score

- Impact: 5
- Confidence: 4
- Effort: 2
- Score: `5 * 4 / 2 = 10.0`
- Verdict: PRODUCTIVE; keep.
