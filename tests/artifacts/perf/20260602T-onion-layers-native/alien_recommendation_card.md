# Alien Recommendation Card: `onion_layers` Native Route

- Bead: `br-r37-c1-l5es6`
- Symptom: public `fnx.onion_layers` delegated to NetworkX after converting the fnx graph, so the profile spent the hot path in `_networkx_graph_for_parity`, `_fnx_to_nx`, and `_topo_emit_edges_by_adj` before running the actual algorithm.
- Profile artifacts:
  - `profile_fallback.txt`
  - `profile_native.txt`
- Baseline: fallback route mean `0.0632563438033685` seconds for BA(3000, 4), 11984 edges, repeat 5.
- Candidate primitive: staged native algorithm dispatch with deterministic graph semantics. This matches the graveyard rule to start from the symptom and remove conversion/layout churn with a narrow drop-in route, using native contiguous graph storage instead of materializing a NetworkX graph.
- EV score: Impact 5 x Confidence 5 x Reuse 3 / Effort 2 x AdoptionFriction 1 = 37.5.
- Selected lever: route the public wrapper to `_fnx.onion_layers_rust` after preserving NetworkX error contracts for directed graphs, multigraphs, and self-loops.
- Fallback: if `_raw_onion_layers` is unavailable, keep `_onion_layers_impl(G)` and delegate to NetworkX.
- Proof obligations:
  - Preserve layer values and result dict insertion order.
  - Preserve error classes/messages for directed, multigraph, and self-loop inputs.
  - Preserve behavior for fnx subgraph views and nx-typed inputs.
  - Preserve deterministic RNG-free output; benchmark graph seed is measurement-only.
