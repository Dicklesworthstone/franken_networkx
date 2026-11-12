# ring_of_cliques single-batch construction — 2.3x slower → ~1.1x (~2.2x self)

Bead: br-r37-c1-ringbatch
Agent: cc / 2026-06-14

ring_of_cliques built the graph with `2*num_cliques` separate
`add_edges_from`/`add_edge` PyO3 calls (one combinations batch + one ring-link
edge per clique). Collapsed to ONE `add_edges_from` over a single edge list
assembled in nx's exact per-clique order (each clique's `combinations` followed
by its ring link), so node/adj insertion order is byte-identical.

Proof: 60-case sweep (num_cliques 2..11 × clique_size 2..7) — `list(nodes)`,
`list(edges)`, and per-node sorted adjacency all == nx, 0 mismatches; error
parity (too-few-cliques / too-small-cliques messages); golden sha256 of edges
(40,10): `f40340e25e6865ac39a7db3b9fcfb06e263493815465a4f07c658d35aa1ac2b5`.
Timing (40,10): 1.98ms → 0.878ms (nx 0.773ms). Pure-Python.
