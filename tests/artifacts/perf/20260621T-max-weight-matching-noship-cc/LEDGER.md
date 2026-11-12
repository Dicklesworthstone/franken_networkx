# NEGATIVE EVIDENCE — max_weight_matching / min_edge_cover 0.81-0.85x is REAL (not the phantom), conversion-tax + order bound

- Agent: `BlackThrush` · 2026-06-21 · (no code change)

## Finding (corrects a prior memory)
A prior note claimed blossom/max_weight_matching/min_edge_cover only LOOK ~2x slow because
the benchmark rebuilt Gfx from edges (destroying nx-generator adj layout), and that
`nx.Graph(G.edges())` is "= fnx parity / phantom". MEASURED with IDENTICAL layout (both
fnx.Graph(edges) AND nx.Graph(SAME edges)): still 0.81-0.85x. Correct result (cover size
125==125). So there is a REAL conversion-tax floor, not parity.

## Why (bound, not fixable cleanly)
- max_weight_matching DELEGATES to nx via _call_networkx_for_parity -> _fnx_to_nx(G). The
  matching itself (nx's blossom) is 99% of min_edge_cover's cost and is 8.3ms; the fnx->nx
  conversion adds ~2ms -> 10.4ms total = 0.81x.
- _fnx_to_nx is ALREADY optimized: native bulk adjacency (_native_fnx_to_nx_adjacency) +
  node-attr dicts + _align_rows. The residual ~2ms is the _align_rows ORDER-PRESERVATION
  pass, which is REQUIRED — a lean `nx.Graph()+add_nodes_from+add_edges_from(data=True)`
  build is 0.67ms but produces a DIFFERENT (order-divergent) matching (verified != current).
- A native Rust blossom can't be used either: matching is order-sensitive (tie-breaks), so
  it yields a different valid matching and fails byte-exact parity (known: stays delegated).

## Conclusion
0.81x is the parity-safe floor: delegate + already-optimized order-preserving conversion.
Beating nx requires a FAITHFUL Rust blossom port replicating nx's exact tie-break order
(substantial, ~200 lines) for a ~2ms gain — not worth it. No ship.
