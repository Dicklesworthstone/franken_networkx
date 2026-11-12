# ego_graph Graph-native result construction rejected

Bead: `br-r37-c1-04z53.18`

Target: `fnx.ego_graph(Graph, 0, radius=2)` on a Barabasi-Albert graph with `n=3000`, `m=4`, `seed=42`.

Profile-backed hotspot: `profile_focused_fnx.txt` showed public `ego_graph` spending `0.474s` over seven calls, dominated by Python result construction through `Graph.add_edge`, graph materialization, and `Graph.add_node`.

Candidate lever: add a guarded PyO3 path for plain undirected `Graph` with integer nonnegative radius, unweighted search, `center=True`, and `undirected=False`, constructing the result graph natively while preserving Python node keys and attrs.

Baseline:
- Focused fnx sample mean: `0.051148625831653284s`.
- Focused fnx sample median: `0.04769608700007666s`.
- NetworkX sample mean: `0.02449930049867059s`.
- Hyperfine process mean: `0.7177s`.
- Golden sha256: `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`.

Candidate:
- Focused fnx sample mean: `0.0944471247518474s`.
- Focused fnx sample median: `0.095774307505053s`.
- Hyperfine process mean: `1.1868467662857145s`.
- Hyperfine process median: `1.18998544s`.
- Golden sha256 stayed `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`.

Restored:
- Focused fnx sample mean: `0.04505393324749699s`.
- Focused fnx sample median: `0.04429722850181861s`.
- Golden sha256 stayed `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`.

Isomorphism proof:
- Ordering: no code was kept; restored route uses the existing Python BFS visit-order and original-edge-order copy path.
- Tie-breaking: no kept neighbor traversal or edge selection policy changed.
- Floating point: none on this unweighted ego graph path.
- RNG: none in library behavior; benchmark graph seed is fixed.
- Golden output: baseline, candidate, and restored samples share the same sha256.

Verdict: rejected. The candidate regressed sampled mean and hyperfine mean, so score is `Impact 1 x Confidence 1 / Effort 2 = 0.5`, below the keep threshold. No `ego_graph` source code is retained.
