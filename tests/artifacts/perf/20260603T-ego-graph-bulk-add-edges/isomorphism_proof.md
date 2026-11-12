# ego_graph Simple Graph Bulk add_edges_from Proof

Bead: `br-r37-c1-04z53.26`

Target: `ego_graph(Graph, 0, radius=2)` on `barabasi_albert_graph(3000, 4, seed=42)`.

## Profile-Backed Target

Baseline cProfile showed 9 `ego_graph` calls taking `0.618s` cumulative. The simple-Graph edge copy spent `0.229s` in the Python `add_edge` wrapper and `0.190s` in raw `Graph.add_edge` for 65682 edge insertions.

## Lever Evaluated

Collect eligible simple-Graph `(u, v, data)` triples in the same `G.edges(data=True)` order and call `graph.add_edges_from(edges_to_add)` once instead of calling `graph.add_edge(u, v, **data)` for every copied edge.

## Behavior Isomorphism

Ordering: candidate edge eligibility was evaluated in the same source `G.edges(data=True)` iteration order, and the collected list preserved that order before `add_edges_from`.

Tie-breaking: BFS node discovery, radius filtering, graph node order, and multigraph behavior were unchanged.

Attribute semantics: the candidate kept the `add_edge(**data)` path for edge data containing non-string keys, preserving the existing keyword-expansion error behavior. Empty and string-keyed dicts were passed through the bulk path.

Floating point: this unweighted radius case performs no floating-point accumulation in the changed path.

RNG: the library path uses no RNG. The benchmark graph seed is fixed at `42`.

Golden output: baseline, NetworkX comparison, candidate repeat-9, candidate repeat-21, and restored runs all emitted digest `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`.

## Benchmark Result

Baseline fnx repeat-9 mean: `0.04547556122027648s`.

NetworkX repeat-9 mean: `0.02331588344370377s`.

Candidate fnx repeat-9 mean: `0.045938352554609686s`.

Candidate fnx repeat-21 mean: `0.04591676633225732s`.

Restored fnx repeat-9 mean: `0.04552073844469204s`.

Hyperfine baseline: `534.9 ms +/- 17.6 ms`.

Hyperfine candidate: `534.7 ms +/- 19.3 ms`.

The focused profile moved `ego_graph` cumulative time from `0.618s` to `0.569s`, but direct samples did not improve and hyperfine was flat.

Score: Impact 1 x Confidence 4 / Effort 4 = 1.0.

Verdict: rejected; no source code kept.
