# br-r37-c1-0e9ey adjacency-data node-key cache

## Kept lever

Cache Python node display objects once per `adjacency_data_simple` call and reuse
them for node rows and neighbor IDs. Traversal order, edge lookup, attr dict
copying, and source attr dict insertion order are unchanged.

## Baseline

- Direct FNX adjacency_data graph mean: `0.016315906203817575s`
- rch/hyperfine FNX adjacency_data graph repeats50 mean: `3.7829363042942856s`
- rch/hyperfine genuine NetworkX repeats50 mean: `3.457061514437143s`

## After

- Direct FNX adjacency_data graph mean: `0.014803686437921392s`
- Direct speedup: `1.102x`
- rch/hyperfine FNX adjacency_data graph repeats50 mean: `3.523837337862857s`
- rch/hyperfine speedup: `1.074x`
- Same-run after FNX vs genuine NetworkX: `3.523837337862857s` vs `3.6117090018628573s`

## Behavior proof

- Baseline proof SHA256: `f7dfafa40a9952d51a498f6d47f9bcaa1a0d526ac60fd4245b757849b33cf304`
- After proof SHA256: `f7dfafa40a9952d51a498f6d47f9bcaa1a0d526ac60fd4245b757849b33cf304`
- Golden output SHA stayed `c6d3b3769d04997423ef53f46ffda7eab920e1a2e2fc79462fb899430db9c5a1`
  for the timed adjacency_data graph case.
- Unsorted JSON/order probe matches genuine NetworkX with SHA
  `9c15cf097c5345bb4e84eb3e75df76fd7dde7cd3ae33ffd43e9e3a9c35289493`.
- Ordering: node and adjacency traversal still use existing `nodes_ordered()` /
  `neighbors_iter()` order; attr dict copies still come from the live PyDict.
- Tie-breaking: no algorithmic tie-breaks in this exporter.
- Floating point: fixture uses integer weights/capacities.
- RNG: fixture is deterministic arithmetic.

## Rejected attempts

- Cache edge export records in `__dict__`: proof-clean but rch node_link_data
  worsened from `0.5250482085228573s` to `0.6964985554885715s`.
- Per-call borrowed edge-attr projection: proof-clean but direct node_link_data
  worsened from `0.008745286101475357s` to `0.010291343541919358s`.
- Broader node-key cache across node_link/to_edgelist was narrowed because
  node_link_data direct timing was neutral/slightly worse.

## Score

Impact `3.0` x Confidence `0.85` / Effort `1.0` = `2.55`. Keep.
