# Native general_random_intersection_graph — delegated → 0.84x (beats nx), completes family

Bead: br-r37-c1-griproj
Agent: cc / 2026-06-14

`general_random_intersection_graph` delegated to nx (`empty_graph` + per-node ×
per-attribute Bernoulli sampling + `projected_graph`) then converted nx→fnx.
Native path (int/None seed) reproduces nx's per-node, per-attribute
`rng.random() < p[attr]` draws over the same node-major iteration, buckets nodes
by attribute, and clique-projects (== nx's shared-attribute edge SET) — skipping
nx's per-edge add_edge + projected_graph + the conversion. `empty_graph(n+m)`
carries no node/graph attrs, so projected nodes (range(n)) have none. Random|numpy
seed delegates; `len(p) != m` raises nx's exact ValueError.

The n×m sequential `random()` draws dominate (inherently same as nx), so the win
is the saved conversion/projection: gri(500,300) ~216ms→157ms vs nx 186ms (0.84x).

Proof: 100-case parity sweep (25 seeds × 4 (n,m), random probability vectors):
full signature (class, graph attrs, sorted nodes w/ attrs, sorted edges) == nx,
0 mismatches; validation parity (`Probability list p must have m elements.`);
golden 81132124...; intersection conformance pass; full suite 22265 pass (6 known
pre-existing). Completes the intersection-graph family (uniform/k_random/general
all native). Pure-Python.
